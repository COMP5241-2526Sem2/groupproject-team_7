import os
import json
import threading
import logging
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.slide import Slide, SlidePage
from app.models.knowledge_point import KnowledgePoint
from app.models.video import Video
from app.models.video_transcript import VideoTranscript
from app.services.ai_service import extract_knowledge_points_from_page

kp_bp = Blueprint("knowledge_points", __name__)
logger = logging.getLogger(__name__)

_STATUS_DIR = None


def _get_status_dir():
    global _STATUS_DIR
    if _STATUS_DIR is None:
        _STATUS_DIR = os.path.join(
            os.environ.get("UPLOAD_FOLDER", "/app/uploads"), "videos"
        )
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


def _run_extraction(app, slide_id):
    """Background worker for KP extraction."""
    with app.app_context():
        try:
            slide = db.session.get(Slide, slide_id)
            if not slide:
                _write_status(slide_id, {"state": "error", "error": "Slide not found"})
                return

            video = (
                Video.query.filter_by(course_id=slide.course_id)
                .order_by(Video.created_at.asc())
                .first()
            )
            total_pages = max(slide.total_pages or len(slide.pages), 1)

            has_transcripts = False
            if video:
                has_transcripts = (
                    VideoTranscript.query
                    .filter_by(video_id=video.id)
                    .filter(VideoTranscript.embedding.isnot(None))
                    .count() > 0
                )

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
                    if has_transcripts and video:
                        try:
                            from app.services.alignment_service import align_knowledge_point
                            kp_text = f"{title}. {content}"
                            timestamp, confidence = align_knowledge_point(kp_text, video.id)
                        except Exception:
                            pass

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

                db.session.commit()

            _write_status(slide_id, {
                "state": "done",
                "created": created_count,
                "message": f"Extracted {created_count} knowledge points",
            })
            logger.info("KP extraction done for slide %s: %d KPs", slide_id, created_count)

        except Exception as e:
            logger.exception("KP extraction failed for slide %s", slide_id)
            _write_status(slide_id, {"state": "error", "error": str(e)})


@kp_bp.route("/extract/<int:slide_id>", methods=["POST"])
def extract_for_slide(slide_id):
    """Start async KP extraction for a slide."""
    slide = db.session.get(Slide, slide_id)
    if not slide:
        return jsonify({"error": "Slide not found"}), 404

    # Check if already running
    status = _read_status(slide_id)
    if status and status.get("state") == "running":
        return jsonify({"message": "Extraction already in progress", "status": status}), 202

    _write_status(slide_id, {"state": "running", "progress": 0, "total": 0, "message": "Starting..."})

    app = current_app._get_current_object()
    t = threading.Thread(target=_run_extraction, args=(app, slide_id), daemon=True)
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
    """Re-align all knowledge points for a course using semantic matching."""
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
    kp = db.session.get(KnowledgePoint, kp_id)
    if not kp:
        return jsonify({"error": "Knowledge point not found"}), 404
    db.session.delete(kp)
    db.session.commit()
    return jsonify({"message": "Knowledge point deleted"})
