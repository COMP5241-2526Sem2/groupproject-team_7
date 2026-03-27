from flask import Blueprint, request, jsonify
from app.services.supabase_repo import (
    select_rows,
    select_one_by_id,
    insert_row,
    update_row_by_id,
    delete_row_by_id,
    serialize_course,
    SupabaseRepoError,
)

courses_bp = Blueprint("courses", __name__)


@courses_bp.route("", methods=["GET"])
def list_courses():
    try:
        courses = select_rows("courses", order_by="created_at", ascending=False)
        payload = []
        for course in courses:
            slides_count = len(select_rows("slides", columns="id", filters=[("eq", "course_id", course["id"])]))
            videos_count = len(select_rows("videos", columns="id", filters=[("eq", "course_id", course["id"])]))
            payload.append(serialize_course(course, slides_count=slides_count, videos_count=videos_count))
        return jsonify(payload)
    except SupabaseRepoError as exc:
        return jsonify({"error": str(exc)}), 500


@courses_bp.route("", methods=["POST"])
def create_course():
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "Title is required"}), 400

    try:
        course = insert_row(
            "courses",
            {
                "title": data["title"],
                "description": data.get("description", ""),
            },
        )
        return jsonify(serialize_course(course, slides_count=0, videos_count=0)), 201
    except SupabaseRepoError as exc:
        return jsonify({"error": str(exc)}), 500


@courses_bp.route("/<int:course_id>", methods=["GET"])
def get_course(course_id):
    course = select_one_by_id("courses", course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404
    slides_count = len(select_rows("slides", columns="id", filters=[("eq", "course_id", course_id)]))
    videos_count = len(select_rows("videos", columns="id", filters=[("eq", "course_id", course_id)]))
    return jsonify(serialize_course(course, slides_count=slides_count, videos_count=videos_count))


@courses_bp.route("/<int:course_id>", methods=["PUT"])
def update_course(course_id):
    course = select_one_by_id("courses", course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    data = request.get_json()
    update_payload = {}
    if data.get("title"):
        update_payload["title"] = data["title"]
    if "description" in data:
        update_payload["description"] = data["description"]

    if update_payload:
        course = update_row_by_id("courses", course_id, update_payload)
    slides_count = len(select_rows("slides", columns="id", filters=[("eq", "course_id", course_id)]))
    videos_count = len(select_rows("videos", columns="id", filters=[("eq", "course_id", course_id)]))
    return jsonify(serialize_course(course, slides_count=slides_count, videos_count=videos_count))


@courses_bp.route("/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    course = select_one_by_id("courses", course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    delete_row_by_id("courses", course_id)
    return jsonify({"message": "Course deleted"})
