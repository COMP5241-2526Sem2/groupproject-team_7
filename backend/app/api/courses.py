from flask import Blueprint, request, jsonify
from sqlalchemy import text
from app import db
from app.models.course import Course
from app.models.knowledge_point import KnowledgePoint
from app.auth_utils import require_teacher

courses_bp = Blueprint("courses", __name__)


@courses_bp.route("", methods=["GET"])
def list_courses():
    courses = Course.query.order_by(Course.created_at.desc()).all()
    return jsonify([c.to_dict() for c in courses])


@courses_bp.route("", methods=["POST"])
def create_course():
    forbidden = require_teacher()
    if forbidden:
        return forbidden

    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "Title is required"}), 400

    course = Course(title=data["title"], description=data.get("description", ""))
    db.session.add(course)
    db.session.commit()
    return jsonify(course.to_dict()), 201


@courses_bp.route("/<int:course_id>", methods=["GET"])
def get_course(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404
    return jsonify(course.to_dict())


@courses_bp.route("/<int:course_id>", methods=["PUT"])
def update_course(course_id):
    forbidden = require_teacher()
    if forbidden:
        return forbidden

    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    data = request.get_json()
    if data.get("title"):
        course.title = data["title"]
    if "description" in data:
        course.description = data["description"]

    db.session.commit()
    return jsonify(course.to_dict())


@courses_bp.route("/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    forbidden = require_teacher()
    if forbidden:
        return forbidden

    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    try:
        # Delete knowledge points for videos in this course using direct SQL
        # to bypass ORM session tracking issues
        video_ids = [v.id for v in course.videos]
        if video_ids:
            db.session.execute(
                text("DELETE FROM knowledge_points WHERE video_id IN :video_ids"),
                {"video_ids": tuple(video_ids)}
            )
        
        # Delete knowledge points for slides in this course
        from app.models.slide import Slide
        slide_ids = [s.id for s in course.slides]
        if slide_ids:
            db.session.execute(
                text("""DELETE FROM knowledge_points WHERE slide_page_id IN (
                    SELECT id FROM slide_pages WHERE slide_id IN :slide_ids
                )"""),
                {"slide_ids": tuple(slide_ids)}
            )
        
        db.session.commit()
        
        # Now delete the course (which will cascade delete slides and videos)
        db.session.delete(course)
        db.session.commit()
        return jsonify({"message": "Course deleted"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
