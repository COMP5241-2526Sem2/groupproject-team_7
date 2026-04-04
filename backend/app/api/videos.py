import os
import uuid
import json
import logging
import subprocess
import shutil
import threading
import time
from urllib.parse import urlparse
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from werkzeug.utils import secure_filename
from app import db
from app.models.video import Video
from app.models.course import Course
from app.models.knowledge_point import KnowledgePoint
from app.auth_utils import require_teacher, require_authenticated, get_request_role

# Try to import cv2 for video duration extraction
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

videos_bp = Blueprint("videos", __name__)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"mp4", "webm", "ogg", "mov"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_extension(filename):
    _, ext = os.path.splitext(filename)
    return ext.lstrip(".").lower()


def _is_external_url(url):
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def _is_supported_external_video_url(url):
    if not _is_external_url(url):
        return False
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()

        # YouTube links (watch, short, embed)
        if host.endswith("youtube.com") or host.endswith("youtu.be"):
            return True

        # Vimeo links
        if host.endswith("vimeo.com"):
            return True

        # Direct video file URLs
        return path.endswith((".mp4", ".webm", ".ogg", ".mov"))
    except Exception:
        return False


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


def _extract_video_thumbnail(video_path, video_id):
    """Extract the first frame of a video as a thumbnail."""
    if not HAS_CV2:
        return
    
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning(f"Could not open video {video_path} for thumbnail extraction")
            return
        
        # Read the first frame
        ret, frame = cap.read()
        if not ret:
            logger.warning(f"Could not read first frame from video {video_path}")
            cap.release()
            return
        
        # Resize frame to reasonable thumbnail size (320x240)
        height, width = frame.shape[:2]
        aspect_ratio = width / height
        thumb_height = 240
        thumb_width = int(thumb_height * aspect_ratio)
        frame_resized = cv2.resize(frame, (thumb_width, thumb_height))
        
        # Save thumbnail
        upload_folder = os.environ.get("UPLOAD_FOLDER", "uploads")
        thumbnails_dir = os.path.join(upload_folder, "videos", "thumbnails")
        os.makedirs(thumbnails_dir, exist_ok=True)
        
        thumbnail_path = os.path.join(thumbnails_dir, f"{video_id}_thumb.jpg")
        cv2.imwrite(thumbnail_path, frame_resized)
        
        logger.info(f"Extracted thumbnail for video {video_id}: {thumbnail_path}")
        cap.release()
    except Exception as e:
        logger.warning(f"Error extracting thumbnail for video {video_id}: {e}")


@videos_bp.route("/upload/init", methods=["POST"])
def init_chunked_upload():
    forbidden = require_authenticated()
    if forbidden:
        return forbidden

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
    forbidden = require_authenticated()
    if forbidden:
        return forbidden

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
    forbidden = require_authenticated()
    if forbidden:
        return forbidden

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
    ext = get_file_extension(meta["filename"])
    if not ext:
        return jsonify({"error": "Invalid file name. Please use a supported video file extension."}), 400
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

    uploader_role = get_request_role()  # Get the user role
    video = Video(
        course_id=meta["course_id"],
        filename=unique_filename,
        original_filename=meta["filename"],
        file_path=file_path,
        uploader_role=uploader_role,
    )
    db.session.add(video)
    db.session.commit()

    # Extract video duration using fallback methods
    try:
        if HAS_CV2:
            # Method 1: Use OpenCV (cv2)
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if fps > 0 and frame_count > 0:
                    duration = frame_count / fps
                    video.duration = float(duration)
                    db.session.commit()
                    logger.info(f"OpenCV: Extracted duration {duration:.2f}s for video {video.id}")
                cap.release()
        else:
            # Method 2: Try ffprobe (if FFmpeg is installed)
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", file_path],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    video.duration = float(result.stdout.strip())
                    db.session.commit()
                    logger.info(f"ffprobe: Extracted duration {video.duration:.2f}s for video {video.id}")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                logger.warning("ffprobe not available, OpenCV not installed, using fallback")
                # Fallback: Set a minimal duration to indicate file exists
                video.duration = 0
                db.session.commit()
    except Exception as e:
        logger.warning("Could not extract video duration: %s", e)
        video.duration = 0
        db.session.commit()

    # Extract keyframe (thumbnail) from video
    try:
        if HAS_CV2:
            _extract_video_thumbnail(file_path, video.id)
    except Exception as e:
        logger.warning("Could not extract video thumbnail: %s", e)

    return jsonify(video.to_dict()), 201


@videos_bp.route("/link", methods=["POST"])
def create_video_link():
    forbidden = require_authenticated()
    if forbidden:
        return forbidden

    data = request.get_json(silent=True) or {}
    course_id = data.get("course_id")
    video_url = (data.get("video_url") or "").strip()
    title = (data.get("title") or "").strip()

    if not course_id:
        return jsonify({"error": "course_id is required"}), 400
    if not _is_external_url(video_url):
        return jsonify({"error": "video_url must be a valid http(s) URL"}), 400
    if not _is_supported_external_video_url(video_url):
        return jsonify({
            "error": "Unsupported external video URL. Please provide a YouTube/Vimeo link or a direct video file URL (.mp4/.webm/.ogg/.mov)."
        }), 400

    course = db.session.get(Course, int(course_id))
    if not course:
        return jsonify({"error": "Course not found"}), 404

    placeholder_name = f"external_{uuid.uuid4().hex}.link"
    uploader_role = get_request_role()
    video = Video(
        course_id=int(course_id),
        filename=placeholder_name,
        original_filename=title or video_url,
        file_path=video_url,
        duration=0,
        processed=False,
        uploader_role=uploader_role,
    )
    db.session.add(video)
    db.session.commit()
    return jsonify(video.to_dict()), 201


@videos_bp.route("/course/<int:course_id>", methods=["GET"])
def get_videos_by_course(course_id):
    query = Video.query.filter_by(course_id=course_id)
    
    # Both students and teachers can only see teacher-uploaded videos
    # Student-uploaded videos are private and not visible to anyone
    query = query.filter_by(uploader_role='teacher')
    
    videos = query.order_by(Video.created_at.desc()).all()
    return jsonify([v.to_dict() for v in videos])


@videos_bp.route("/<int:video_id>", methods=["GET"])
def get_video(video_id):
    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404
    return jsonify(video.to_dict())


@videos_bp.route("/<int:video_id>/thumbnail", methods=["GET"])
def get_video_thumbnail(video_id):
    """Get the thumbnail image for a video."""
    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404
    
    upload_folder = os.environ.get("UPLOAD_FOLDER", "uploads")
    thumbnails_dir = os.path.join(upload_folder, "videos", "thumbnails")
    thumbnail_path = os.path.join(thumbnails_dir, f"{video_id}_thumb.jpg")
    
    if not os.path.exists(thumbnail_path):
        # No thumbnail generated, return 404
        return jsonify({"error": "Thumbnail not available"}), 404
    
    return send_from_directory(thumbnails_dir, f"{video_id}_thumb.jpg")


@videos_bp.route("/stream/<path:filename>", methods=["GET"])
def stream_video(filename):
    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "videos")
    return send_from_directory(upload_dir, filename)


@videos_bp.route("/<int:video_id>", methods=["DELETE"])
def delete_video(video_id):
    forbidden = require_authenticated()
    if forbidden:
        return forbidden

    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    user_role = get_request_role()

    # Teachers can delete any video.
    # Students can only delete videos they uploaded.
    if user_role == "student" and video.uploader_role != "student":
        return jsonify({"error": "Forbidden: you can only delete videos you uploaded"}), 403

    # Break FK references from knowledge points before deleting the video.
    # Keep knowledge points, but clear their video alignment.
    KnowledgePoint.query.filter_by(video_id=video.id).update(
        {"video_id": None, "video_timestamp": None, "confidence": 0.0},
        synchronize_session=False,
    )

    if os.path.exists(video.file_path):
        os.remove(video.file_path)

    db.session.delete(video)
    db.session.commit()
    return jsonify({"message": "Video deleted"})


def _asr_status_path(video_id):
    return os.path.join(current_app.config["UPLOAD_FOLDER"], "videos", f"_asr_status_{video_id}.json")


def _read_asr_status(video_id):
    path = _asr_status_path(video_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as handle:
            return json.load(handle)
    except Exception:
        return None


def _write_asr_status(video_id, payload):
    path = _asr_status_path(video_id)
    with open(path, "w") as handle:
        json.dump(payload, handle)


@videos_bp.route("/<int:video_id>/transcribe", methods=["POST"])
def transcribe(video_id):
    forbidden = require_authenticated()
    if forbidden:
        return forbidden

    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404
    if video.is_external():
        return jsonify({"error": "External video links cannot be transcribed. Please upload the video file instead."}), 400

    status_file = _asr_status_path(video_id)
    if os.path.exists(status_file):
        status = _read_asr_status(video_id) or {}
        if status.get("state") == "running" and time.time() - float(status.get("started_at", 0) or 0) < 600:
            return jsonify({"message": "Transcription already in progress"}), 202

    started_at = time.time()
    _write_asr_status(video_id, {
        "state": "running",
        "error": None,
        "segments": 0,
        "started_at": started_at,
        "progress": 0,
        "message": "Starting...",
    })

    app = current_app._get_current_object()

    def _run_asr():
        with app.app_context():
            try:
                from app.services.alignment_service import transcribe_video as do_transcribe

                def _on_progress(stage, percent, message):
                    _write_asr_status(video_id, {
                        "state": "running",
                        "error": None,
                        "segments": 0,
                        "started_at": started_at,
                        "stage": stage,
                        "progress": percent,
                        "message": message,
                    })

                result = do_transcribe(video_id, progress_cb=_on_progress)
                if isinstance(result, dict) and result.get("error"):
                    _write_asr_status(video_id, {"state": "error", "error": result["error"], "segments": 0, "progress": 0})
                else:
                    _write_asr_status(video_id, {"state": "done", "error": None, "segments": len(result), "progress": 100})
            except Exception as exc:
                logger.exception("Background ASR failed for video %s", video_id)
                _write_asr_status(video_id, {"state": "error", "error": str(exc), "segments": 0, "progress": 0})

    threading.Thread(target=_run_asr, daemon=True).start()
    return jsonify({"message": "Transcription started"}), 202


@videos_bp.route("/<int:video_id>/transcribe/status", methods=["GET"])
def transcribe_status(video_id):
    status = _read_asr_status(video_id)
    if not status:
        return jsonify({"state": "idle", "error": None, "segments": 0})
    if status.get("state") == "running":
        started_at = float(status.get("started_at", 0) or 0)
        if started_at and time.time() - started_at > 600:
            status["state"] = "error"
            status["error"] = "Transcription timed out. Please retry."
            _write_asr_status(video_id, status)
    return jsonify(status)


@videos_bp.route("/<int:video_id>/transcribe/cancel", methods=["POST"])
def cancel_transcribe(video_id):
    forbidden = require_authenticated()
    if forbidden:
        return forbidden

    status_file = _asr_status_path(video_id)
    if os.path.exists(status_file):
        os.remove(status_file)
    return jsonify({"message": "Transcription cancelled. You can retry now."})


@videos_bp.route("/<int:video_id>/transcript", methods=["GET"])
def get_transcript(video_id):
    video = db.session.get(Video, video_id)
    if not video:
        return jsonify({"error": "Video not found"}), 404
    if video.is_external():
        return jsonify({"error": "External video links do not have transcripts"}), 400

    from app.services.alignment_service import get_video_transcript

    return jsonify(get_video_transcript(video_id))


