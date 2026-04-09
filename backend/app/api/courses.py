from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from app import db
from app.models.course import Course
from app.models.knowledge_point import KnowledgePoint
from app.models.quiz import Quiz, QuizAttempt
from app.models.slide import SlidePage
from app.models.video_transcript import VideoTranscript
from app.models.chat import ChatMessage
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
        video_ids = [v.id for v in course.videos]
        slide_ids = [s.id for s in course.slides]

        kp_ids = []
        if video_ids or slide_ids:
            filters = []
            if video_ids:
                filters.append(KnowledgePoint.video_id.in_(video_ids))
            if slide_ids:
                slide_page_ids = [
                    row[0]
                    for row in db.session.query(SlidePage.id)
                    .filter(SlidePage.slide_id.in_(slide_ids))
                    .all()
                ]
                if slide_page_ids:
                    filters.append(KnowledgePoint.slide_page_id.in_(slide_page_ids))

            if filters:
                kp_ids = [
                    row[0]
                    for row in db.session.query(KnowledgePoint.id)
                    .filter(or_(*filters))
                    .all()
                ]

        # Delete dependent quizzes (and attempts) before deleting knowledge points.
        if kp_ids:
            quiz_ids = [
                row[0]
                for row in db.session.query(Quiz.id)
                .filter(Quiz.knowledge_point_id.in_(kp_ids))
                .all()
            ]
            if quiz_ids:
                QuizAttempt.query.filter(QuizAttempt.quiz_id.in_(quiz_ids)).delete(
                    synchronize_session=False
                )
                Quiz.query.filter(Quiz.id.in_(quiz_ids)).delete(
                    synchronize_session=False
                )

            KnowledgePoint.query.filter(KnowledgePoint.id.in_(kp_ids)).delete(
                synchronize_session=False
            )

        # Delete dependent transcripts before deleting videos via course cascade.
        if video_ids:
            VideoTranscript.query.filter(VideoTranscript.video_id.in_(video_ids)).delete(
                synchronize_session=False
            )

        # Delete chat messages for this course
        ChatMessage.query.filter(ChatMessage.course_id == course_id).delete(
            synchronize_session=False
        )

        # Now delete the course (slides/videos still cascade through ORM relationships).
        db.session.delete(course)
        db.session.commit()
        return jsonify({"message": "Course deleted"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
