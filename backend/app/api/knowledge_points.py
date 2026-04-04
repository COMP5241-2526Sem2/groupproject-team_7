import os
import json
import threading
import logging
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.slide import Slide, SlidePage
from app.models.knowledge_point import KnowledgePoint
from app.models.video import Video
from app.models.quiz import Quiz
from app.services.ai_service import extract_knowledge_points_from_page
from app.auth_utils import require_authenticated, require_teacher

kp_bp = Blueprint("knowledge_points", __name__)
logger = logging.getLogger(__name__)

_STATUS_DIR = None


def _get_status_dir():
    global _STATUS_DIR
    if _STATUS_DIR is None:
        try:
            upload_root = current_app.config.get("UPLOAD_FOLDER")
        except RuntimeError:
            upload_root = None

        if not upload_root:
            upload_root = os.path.abspath(os.environ.get("UPLOAD_FOLDER", "uploads"))

        _STATUS_DIR = os.path.join(upload_root, "videos")
        os.makedirs(_STATUS_DIR, exist_ok=True)
    return _STATUS_DIR


def _status_path(slide_id):
    return os.path.join(_get_status_dir(), f"_kp_status_{slide_id}.json")


def _write_status(slide_id, data):
    path = _status_path(slide_id)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def _read_status(slide_id):
    path = _status_path(slide_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _select_alignment_video(slide, preferred_video_id=None):
    # Try to use preferred video if it has duration
    if preferred_video_id is not None:
        preferred = db.session.get(Video, preferred_video_id)
        if preferred and preferred.course_id == slide.course_id and preferred.duration and preferred.duration > 0:
            return preferred

    # Get all videos for the course, sorted by creation date (newest first)
    videos = (
        Video.query.filter_by(course_id=slide.course_id)
        .order_by(Video.created_at.desc())
        .all()
    )
    if not videos:
        return None
    
    # Prefer videos with duration > 0 (local uploads usually have duration, external links often don't)
    for video in videos:
        if video.duration and video.duration > 0:
            return video

    # If no video has duration, return the latest one anyway (it might succeed if duration is available)
    return videos[0]


def _run_extraction(app, slide_id, preferred_video_id=None):
    """Background worker for KP extraction."""
    with app.app_context():
        try:
            slide = db.session.get(Slide, slide_id)
            if not slide:
                _write_status(slide_id, {"state": "error", "error": "Slide not found"})
                return

            video = _select_alignment_video(slide, preferred_video_id=preferred_video_id)
            total_pages = max(slide.total_pages or len(slide.pages), 1)

            pages_to_process = []
            for page in sorted(slide.pages, key=lambda p: p.page_number):
                existing = KnowledgePoint.query.filter_by(slide_page_id=page.id).count()
                if existing == 0:
                    pages_to_process.append(page)

            if not pages_to_process:
                _write_status(slide_id, {
                    "state": "done", "created": 0,
                    "message": "All pages already have knowledge points",
                })
                return

            total = len(pages_to_process)
            created_count = 0
            aligned_count = 0

            for idx, page in enumerate(pages_to_process):
                _write_status(slide_id, {
                    "state": "running",
                    "progress": idx,
                    "total": total,
                    "message": f"Processing page {page.page_number} ({idx+1}/{total})",
                })

                kp_data_list = extract_knowledge_points_from_page(page)
                for kp_data in kp_data_list:
                    title = kp_data.get("title", "Untitled")[:300]
                    content = kp_data.get("content", "")

                    timestamp = None
                    confidence = 0.0

                    if timestamp is None and video and video.duration and video.duration > 0:
                        fraction = (page.page_number - 1) / total_pages
                        timestamp = round(fraction * video.duration, 1)
                        confidence = 0.3

                    kp = KnowledgePoint(
                        slide_page_id=page.id,
                        video_id=video.id if video else None,
                        title=title,
                        content=content,
                        video_timestamp=timestamp,
                        confidence=confidence,
                    )
                    db.session.add(kp)
                    created_count += 1
                    if timestamp is not None:
                        aligned_count += 1

                db.session.commit()

            message = f"Extracted {created_count} knowledge points"
            if created_count > 0 and aligned_count == 0:
                if not video:
                    message += " (no course video found; upload a video to enable timestamp alignment)"
                else:
                    message += " (no video-aligned timestamps; ensure the selected video has duration metadata)"

            _write_status(slide_id, {
                "state": "done",
                "created": created_count,
                "aligned": aligned_count,
                "message": message,
            })
            logger.info("KP extraction done for slide %s: %d KPs", slide_id, created_count)

        except Exception as e:
            logger.exception("KP extraction failed for slide %s", slide_id)
            _write_status(slide_id, {"state": "error", "error": str(e)})


@kp_bp.route("/extract/<int:slide_id>", methods=["POST"])
def extract_for_slide(slide_id):
    """Start async KP extraction for a slide."""
    forbidden = require_authenticated()
    if forbidden:
        return forbidden

    slide = db.session.get(Slide, slide_id)
    if not slide:
        return jsonify({"error": "Slide not found"}), 404

    force = request.args.get("force", "0").lower() in ("1", "true", "yes")
    preferred_video_id = request.args.get("video_id", type=int)

    if preferred_video_id is not None:
        preferred_video = db.session.get(Video, preferred_video_id)
        if not preferred_video:
            return jsonify({"error": "Preferred video not found"}), 404
        if preferred_video.course_id != slide.course_id:
            return jsonify({"error": "Preferred video does not belong to this course"}), 400

    # Check if already running
    status = _read_status(slide_id)
    if status and status.get("state") == "running":
        return jsonify({"message": "Extraction already in progress", "status": status}), 202

    if force:
        page_ids = [p.id for p in slide.pages]
        if page_ids:
            # Get KnowledgePoint IDs that need to be deleted
            kp_ids = [
                kp.id for kp in KnowledgePoint.query
                .filter(KnowledgePoint.slide_page_id.in_(page_ids))
                .all()
            ]
            
            if kp_ids:
                # First delete associated quizzes
                Quiz.query.filter(Quiz.knowledge_point_id.in_(kp_ids)).delete(
                    synchronize_session=False
                )
                # Then delete knowledge points
                KnowledgePoint.query.filter(KnowledgePoint.id.in_(kp_ids)).delete(
                    synchronize_session=False
                )
                db.session.commit()

    _write_status(slide_id, {"state": "running", "progress": 0, "total": 0, "message": "Starting..."})

    app = current_app._get_current_object()
    t = threading.Thread(
        target=_run_extraction,
        args=(app, slide_id, preferred_video_id),
        daemon=True,
    )
    t.start()

    return jsonify({"message": "KP extraction started", "status": {"state": "running"}}), 202


@kp_bp.route("/extract/<int:slide_id>/status", methods=["GET"])
def extract_status(slide_id):
    """Poll extraction status."""
    status = _read_status(slide_id)
    if not status:
        return jsonify({"state": "idle"})
    return jsonify(status)


@kp_bp.route("/align/<int:course_id>", methods=["POST"])
def realign_course(course_id):
    """Re-align all knowledge points for a course using video duration."""
    forbidden = require_teacher()
    if forbidden:
        return forbidden

    from app.services.alignment_service import align_all_knowledge_points
    result = align_all_knowledge_points(course_id)
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@kp_bp.route("/course/<int:course_id>", methods=["GET"])
def get_by_course(course_id):
    """Get all knowledge points for a course."""
    slides = Slide.query.filter_by(course_id=course_id).all()
    page_ids = []
    for s in slides:
        page_ids.extend([p.id for p in s.pages])

    if not page_ids:
        return jsonify([])

    kps = (
        KnowledgePoint.query.filter(KnowledgePoint.slide_page_id.in_(page_ids))
        .order_by(KnowledgePoint.id.asc())
        .all()
    )
    return jsonify([kp.to_dict() for kp in kps])


@kp_bp.route("/page/<int:page_id>", methods=["GET"])
def get_by_page(page_id):
    """Get knowledge points for a specific slide page."""
    kps = KnowledgePoint.query.filter_by(slide_page_id=page_id).all()
    return jsonify([kp.to_dict() for kp in kps])


@kp_bp.route("/<int:kp_id>", methods=["DELETE"])
def delete_kp(kp_id):
    forbidden = require_teacher()
    if forbidden:
        return forbidden

    kp = db.session.get(KnowledgePoint, kp_id)
    if not kp:
        return jsonify({"error": "Knowledge point not found"}), 404
    db.session.delete(kp)
    db.session.commit()
    return jsonify({"message": "Knowledge point deleted"})
