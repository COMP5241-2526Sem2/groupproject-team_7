import os
import uuid
import json
import logging
import subprocess
import shutil
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from werkzeug.utils import secure_filename
from app import db
from app.models.video import Video
from app.models.course import Course

videos_bp = Blueprint("videos", __name__)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"mp4", "webm", "ogg", "mov"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _chunk_dir(upload_id):
    """Return the chunk directory path for a given upload_id."""
    upload_folder = os.environ.get("UPLOAD_FOLDER", "uploads")
    return os.path.join(upload_folder, "videos", f"_chunks_{upload_id}")


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
    """Merge chunks and create the video record."""
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
    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "videos")
    file_path = os.path.join(upload_dir, unique_filename)

    # Merge chunks in order
    cdir = _chunk_dir(upload_id)
    with open(file_path, "wb") as out:
        for i in range(meta["total_chunks"]):
            chunk_path = os.path.join(cdir, f"chunk_{i:06d}")
            with open(chunk_path, "rb") as cp:
                shutil.copyfileobj(cp, out)

    # Clean up chunk directory
    shutil.rmtree(cdir, ignore_errors=True)

    video = Video(
        course_id=meta["course_id"],
        filename=unique_filename,
        original_filename=meta["filename"],
        file_path=file_path,
    )
    db.session.add(video)
    db.session.commit()

    # Extract video duration using ffprobe
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            video.duration = float(result.stdout.strip())
            db.session.commit()
    except Exception as e:
        logger.warning("Could not extract video duration: %s", e)

    return jsonify(video.to_dict()), 201


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


@videos_bp.route("/stream/<path:filename>", methods=["GET"])
def stream_video(filename):
    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "videos")
    return send_from_directory(upload_dir, filename)


@videos_bp.route("/<int:video_id>", methods=["DELETE"])
def delete_video(video_id):
    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    if os.path.exists(video.file_path):
        os.remove(video.file_path)

    db.session.delete(video)
    db.session.commit()
    return jsonify({"message": "Video deleted"})


@videos_bp.route("/<int:video_id>/transcribe", methods=["POST"])
def transcribe(video_id):
    """Start ASR transcription in a background thread.

    Returns immediately; client should poll GET /<video_id>/transcribe/status.
    """
    import threading
    import time as _time

    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    # Prevent duplicate runs
    status_file = os.path.join(
        current_app.config["UPLOAD_FOLDER"], "videos", f"_asr_status_{video_id}.json"
    )
    if os.path.exists(status_file):
        with open(status_file) as f:
            status = json.load(f)
        if status.get("state") == "running":
            # Check if the running process is stale (> 30 minutes old)
            started_at = status.get("started_at", 0)
            if _time.time() - started_at < 1800:
                return jsonify({"message": "Transcription already in progress"}), 202
            # Stale — allow restart
            logger.warning("Stale ASR status detected for video %s, restarting", video_id)

    # Write initial status
    started_at = _time.time()
    with open(status_file, "w") as f:
        json.dump({"state": "running", "error": None, "segments": 0, "started_at": started_at, "progress": 0, "message": "Starting..."}, f)

    # Capture app for background thread
    app = current_app._get_current_object()

    def _run_asr():
        with app.app_context():
            try:
                logger.info("Background ASR thread started for video %s", video_id)
                from app.services.alignment_service import transcribe_video as do_transcribe

                def _on_progress(stage, percent, message):
                    with open(status_file, "w") as f:
                        json.dump({
                            "state": "running",
                            "error": None,
                            "segments": 0,
                            "started_at": started_at,
                            "stage": stage,
                            "progress": percent,
                            "message": message,
                        }, f)

                result = do_transcribe(video_id, progress_cb=_on_progress)
                if isinstance(result, dict) and "error" in result:
                    logger.error("ASR returned error for video %s: %s", video_id, result["error"])
                    with open(status_file, "w") as f:
                        json.dump({"state": "error", "error": result["error"], "segments": 0, "progress": 0}, f)
                else:
                    logger.info("ASR completed for video %s: %d segments", video_id, len(result))
                    with open(status_file, "w") as f:
                        json.dump({"state": "done", "error": None, "segments": len(result), "progress": 100}, f)
            except Exception as exc:
                logger.exception("Background ASR failed for video %s", video_id)
                with open(status_file, "w") as f:
                    json.dump({"state": "error", "error": str(exc), "segments": 0, "progress": 0}, f)

    t = threading.Thread(target=_run_asr, daemon=True)
    t.start()

    return jsonify({"message": "Transcription started"}), 202


@videos_bp.route("/<int:video_id>/transcribe/status", methods=["GET"])
def transcribe_status(video_id):
    """Poll the status of an ongoing ASR transcription."""
    import time as _time
    status_file = os.path.join(
        current_app.config["UPLOAD_FOLDER"], "videos", f"_asr_status_{video_id}.json"
    )
    if not os.path.exists(status_file):
        return jsonify({"state": "idle", "error": None, "segments": 0})
    with open(status_file) as f:
        data = json.load(f)
    # Auto-detect stuck "running" state (>30 min)
    if data.get("state") == "running":
        started_at = data.get("started_at", 0)
        if started_at and _time.time() - started_at > 1800:
            data["state"] = "error"
            data["error"] = "Transcription timed out (possibly out of memory). Try a shorter video or use the 'tiny' model."
            with open(status_file, "w") as f:
                json.dump(data, f)
    return jsonify(data)


@videos_bp.route("/<int:video_id>/transcript", methods=["GET"])
def get_transcript(video_id):
    """Get the transcript segments for a video."""
    from app.services.alignment_service import get_video_transcript

    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    segments = get_video_transcript(video_id)
    return jsonify(segments)
