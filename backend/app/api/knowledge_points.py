import os
import json
import threading
import logging
from flask import Blueprint, jsonify, current_app

from app.services.ai_service import extract_knowledge_points_from_page
from app.services.supabase_repo import (
    select_rows,
    select_one_by_id,
    insert_row,
    delete_row_by_id,
    serialize_knowledge_point,
)

kp_bp = Blueprint("knowledge_points", __name__)
logger = logging.getLogger(__name__)

_STATUS_DIR = None


def _get_status_dir():
    global _STATUS_DIR
    if _STATUS_DIR is None:
        _STATUS_DIR = os.path.join(os.environ.get("UPLOAD_FOLDER", "/app/uploads"), "videos")
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
            slide = select_one_by_id("slides", slide_id)
            if not slide:
                _write_status(slide_id, {"state": "error", "error": "Slide not found"})
                return

            videos = select_rows(
                "videos",
                filters=[("eq", "course_id", slide["course_id"])],
                order_by="created_at",
                ascending=True,
                limit=1,
            )
            video = videos[0] if videos else None

            slide_pages = select_rows(
                "slide_pages",
                filters=[("eq", "slide_id", slide_id)],
                order_by="page_number",
                ascending=True,
            )
            total_pages = max(slide.get("total_pages") or len(slide_pages), 1)

            has_transcripts = False
            if video:
                transcripts = select_rows(
                    "video_transcripts",
                    columns="id",
                    filters=[("eq", "video_id", video["id"]), ("not.is", "embedding", None)],
                )
                has_transcripts = len(transcripts) > 0

            pages_to_process = []
            for page in slide_pages:
                existing = select_rows(
                    "knowledge_points",
                    columns="id",
                    filters=[("eq", "slide_page_id", page["id"])],
                )
                if not existing:
                    pages_to_process.append(page)

            if not pages_to_process:
                _write_status(
                    slide_id,
                    {
                        "state": "done",
                        "created": 0,
                        "message": "All pages already have knowledge points",
                    },
                )
                return

            total = len(pages_to_process)
            created_count = 0

            for idx, page in enumerate(pages_to_process):
                _write_status(
                    slide_id,
                    {
                        "state": "running",
                        "progress": idx,
                        "total": total,
                        "message": f"Processing page {page['page_number']} ({idx + 1}/{total})",
                    },
                )

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
                            timestamp, confidence = align_knowledge_point(kp_text, video["id"])
                        except Exception:
                            pass

                    if timestamp is None and video and video.get("duration") and video.get("duration") > 0:
                        fraction = (page["page_number"] - 1) / total_pages
                        timestamp = round(fraction * video["duration"], 1)
                        confidence = 0.3

                    insert_row(
                        "knowledge_points",
                        {
                            "slide_page_id": page["id"],
                            "video_id": video["id"] if video else None,
                            "title": title,
                            "content": content,
                            "video_timestamp": timestamp,
                            "confidence": confidence,
                        },
                    )
                    created_count += 1

            _write_status(
                slide_id,
                {
                    "state": "done",
                    "created": created_count,
                    "message": f"Extracted {created_count} knowledge points",
                },
            )
            logger.info("KP extraction done for slide %s: %d KPs", slide_id, created_count)

        except Exception as e:
            logger.exception("KP extraction failed for slide %s", slide_id)
            _write_status(slide_id, {"state": "error", "error": str(e)})


@kp_bp.route("/extract/<int:slide_id>", methods=["POST"])
def extract_for_slide(slide_id):
    """Start async KP extraction for a slide."""
    slide = select_one_by_id("slides", slide_id, columns="id")
    if not slide:
        return jsonify({"error": "Slide not found"}), 404

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
    slides = select_rows("slides", columns="id", filters=[("eq", "course_id", course_id)])
    page_ids = []
    pages_by_id = {}
    for slide in slides:
        pages = select_rows("slide_pages", filters=[("eq", "slide_id", slide["id"])])
        for page in pages:
            page_ids.append(page["id"])
            pages_by_id[page["id"]] = page

    if not page_ids:
        return jsonify([])

    kps = select_rows(
        "knowledge_points",
        filters=[("in", "slide_page_id", page_ids)],
        order_by="id",
        ascending=True,
    )
    return jsonify([serialize_knowledge_point(kp, pages_by_id.get(kp["slide_page_id"])) for kp in kps])


@kp_bp.route("/page/<int:page_id>", methods=["GET"])
def get_by_page(page_id):
    """Get knowledge points for a specific slide page."""
    page = select_one_by_id("slide_pages", page_id)
    kps = select_rows("knowledge_points", filters=[("eq", "slide_page_id", page_id)])
    return jsonify([serialize_knowledge_point(kp, page) for kp in kps])


@kp_bp.route("/<int:kp_id>", methods=["DELETE"])
def delete_kp(kp_id):
    kp = select_one_by_id("knowledge_points", kp_id, columns="id")
    if not kp:
        return jsonify({"error": "Knowledge point not found"}), 404
    delete_row_by_id("knowledge_points", kp_id)
    return jsonify({"message": "Knowledge point deleted"})
