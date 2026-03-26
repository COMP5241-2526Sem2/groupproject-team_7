import os
import uuid
import json
import logging
import subprocess
import shutil
import tempfile
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app import db
from app.models.video import Video
from app.models.course import Course
from app.services.s3_service import get_s3_service

videos_bp = Blueprint("videos", __name__)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"mp4", "webm", "ogg", "mov"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _chunk_dir(upload_id):
    """Return the chunk directory path for a given upload_id (in temp directory)."""
    temp_dir = current_app.config.get("TEMP_UPLOAD_DIR", "/tmp/synclearn_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    return os.path.join(temp_dir, f"videos_chunks_{upload_id}")


def _meta_path(upload_id):
    """Return the metadata JSON file path for a given upload_id."""
    return os.path.join(_chunk_dir(upload_id), "_meta.json")


def _save_meta(upload_id, meta):
    with open(_meta_path(upload_id), "w") as f:
        json.dump(meta, f)


def _load_meta(upload_id):
    mp = _meta_path(upload_id)
    if not os.path.exists(mp):
        return None
    with open(mp) as f:
        return json.load(f)


@videos_bp.route("/upload/init", methods=["POST"])
def init_chunked_upload():
    """Initialise a chunked upload session."""
    data = request.get_json(force=True)
    filename = data.get("filename", "")
    course_id = data.get("course_id")
    total_chunks = data.get("total_chunks", 1)

    if not filename or not allowed_file(filename):
        return jsonify({"error": "Unsupported video format. Use MP4, WebM, OGG, or MOV."}), 400
    if not course_id:
        return jsonify({"error": "course_id is required"}), 400

    course = db.session.get(Course, int(course_id))
    if not course:
        return jsonify({"error": "Course not found"}), 404

    upload_id = uuid.uuid4().hex
    os.makedirs(_chunk_dir(upload_id), exist_ok=True)

    _save_meta(upload_id, {
        "filename": filename,
        "course_id": int(course_id),
        "total_chunks": int(total_chunks),
        "received": [],
    })
    return jsonify({"upload_id": upload_id}), 200


@videos_bp.route("/upload/chunk", methods=["POST"])
def upload_chunk():
    """Receive a single chunk."""
    upload_id = request.form.get("upload_id")
    chunk_index = request.form.get("chunk_index")

    if not upload_id:
        return jsonify({"error": "Invalid upload_id"}), 400

    meta = _load_meta(upload_id)
    if meta is None:
        return jsonify({"error": "Invalid upload_id"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No chunk data"}), 400

    chunk = request.files["file"]
    idx = int(chunk_index)
    chunk_path = os.path.join(_chunk_dir(upload_id), f"chunk_{idx:06d}")
    chunk.save(chunk_path)

    if idx not in meta["received"]:
        meta["received"].append(idx)
        _save_meta(upload_id, meta)

    return jsonify({"received": idx, "total_received": len(meta["received"])}), 200


@videos_bp.route("/upload/complete", methods=["POST"])
def complete_chunked_upload():
    """Merge chunks and upload the video to S3."""
    from io import BytesIO
    
    data = request.get_json(force=True)
    upload_id = data.get("upload_id")

    if not upload_id:
        return jsonify({"error": "Invalid upload_id"}), 400

    meta = _load_meta(upload_id)
    if meta is None:
        return jsonify({"error": "Invalid upload_id"}), 400

    if len(meta["received"]) < meta["total_chunks"]:
        return jsonify({"error": f"Missing chunks: received {len(meta['received'])}/{meta['total_chunks']}"}), 400

    original_filename = secure_filename(meta["filename"])
    ext = original_filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    s3_key = f"videos/{int(meta['course_id'])}/{unique_filename}"
    
    # Create temp file to merge chunks
    temp_dir = current_app.config.get("TEMP_UPLOAD_DIR", "/tmp/synclearn_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    temp_video_path = os.path.join(temp_dir, f"merged_{upload_id}.{ext}")

    try:
        # Merge chunks in order
        cdir = _chunk_dir(upload_id)
        with open(temp_video_path, "wb") as out:
            for i in range(meta["total_chunks"]):
                chunk_path = os.path.join(cdir, f"chunk_{i:06d}")
                with open(chunk_path, "rb") as cp:
                    shutil.copyfileobj(cp, out)

        # Clean up chunk directory
        shutil.rmtree(cdir, ignore_errors=True)

        # Upload merged video to S3
        s3_service = get_s3_service()
        with open(temp_video_path, "rb") as f:
            s3_service.upload_file(f, s3_key, content_type="video/mp4")

        # Create video record with S3 key
        video = Video(
            course_id=meta["course_id"],
            filename=unique_filename,
            original_filename=original_filename,
            file_path=s3_key,  # Store S3 key, not local path
        )
        db.session.add(video)
        db.session.commit()

        # Extract video duration using ffprobe on temp file
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", temp_video_path],
                capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                video.duration = float(result.stdout.strip())
                db.session.commit()
        except Exception as e:
            logger.warning("Could not extract video duration: %s", e)

        return jsonify(video.to_dict()), 201
    finally:
        # Clean up temp file
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)


@videos_bp.route("/course/<int:course_id>", methods=["GET"])
def get_videos_by_course(course_id):
    videos = Video.query.filter_by(course_id=course_id).order_by(Video.created_at.desc()).all()
    return jsonify([v.to_dict() for v in videos])


@videos_bp.route("/<int:video_id>", methods=["GET"])
def get_video(video_id):
    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404
    return jsonify(video.to_dict())


@videos_bp.route("/stream/<int:video_id>", methods=["GET"])
def get_video_stream_url(video_id):
    """Get presigned URL for streaming/downloading video from S3."""
    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404
    
    try:
        s3_service = get_s3_service()
        presigned_url = s3_service.generate_presigned_url(video.file_path, expiration=3600)
        return jsonify({"url": presigned_url, "original_filename": video.original_filename})
    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return jsonify({"error": "Failed to generate stream URL"}), 500


@videos_bp.route("/<int:video_id>", methods=["DELETE"])
def delete_video(video_id):
    """Delete a video from S3."""
    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    try:
        s3_service = get_s3_service()
        s3_service.delete_file(video.file_path)
    except Exception as e:
        logger.error(f"Failed to delete video from S3: {e}")
        return jsonify({"error": "Failed to delete video"}), 500

    db.session.delete(video)
    db.session.commit()
    return jsonify({"message": "Video deleted"})


@videos_bp.route("/<int:video_id>/transcribe", methods=["POST"])
def transcribe(video_id):
    """Start ASR transcription in a background thread.

    Returns immediately; client should poll GET /<video_id>/transcribe/status.
    """
    import threading

    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    # Prevent duplicate runs - status stored in temp directory
    temp_dir = current_app.config.get("TEMP_UPLOAD_DIR", "/tmp/synclearn_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    status_file = os.path.join(temp_dir, f"asr_status_{video_id}.json")
    
    if os.path.exists(status_file):
        with open(status_file) as f:
            status = json.load(f)
        if status.get("state") == "running":
            return jsonify({"message": "Transcription already in progress"}), 202

    # Write initial status
    with open(status_file, "w") as f:
        json.dump({"state": "running", "error": None, "segments": 0}, f)

    # Capture app for background thread
    app = current_app._get_current_object()

    def _run_asr():
        with app.app_context():
            try:
                from app.services.alignment_service import transcribe_video as do_transcribe
                result = do_transcribe(video_id)
                if isinstance(result, dict) and "error" in result:
                    with open(status_file, "w") as f:
                        json.dump({"state": "error", "error": result["error"], "segments": 0}, f)
                else:
                    with open(status_file, "w") as f:
                        json.dump({"state": "done", "error": None, "segments": len(result)}, f)
            except Exception as exc:
                logger.error("Background ASR failed: %s", exc)
                with open(status_file, "w") as f:
                    json.dump({"state": "error", "error": str(exc), "segments": 0}, f)

    t = threading.Thread(target=_run_asr, daemon=True)
    t.start()

    return jsonify({"message": "Transcription started"}), 202


@videos_bp.route("/<int:video_id>/transcribe/status", methods=["GET"])
def transcribe_status(video_id):
    """Poll the status of an ongoing ASR transcription."""
    temp_dir = current_app.config.get("TEMP_UPLOAD_DIR", "/tmp/synclearn_uploads")
    status_file = os.path.join(temp_dir, f"asr_status_{video_id}.json")
    
    if not os.path.exists(status_file):
        return jsonify({"state": "idle", "error": None, "segments": 0})
    with open(status_file) as f:
        return jsonify(json.load(f))


@videos_bp.route("/<int:video_id>/transcript", methods=["GET"])
def get_transcript(video_id):
    """Get the transcript segments for a video."""
    from app.services.alignment_service import get_video_transcript

    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    segments = get_video_transcript(video_id)
    return jsonify(segments)
