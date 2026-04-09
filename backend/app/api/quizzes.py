from flask import Blueprint, request, jsonify
from app import db
from app.models.quiz import Quiz, QuizAttempt
from app.models.course import Course
from app.models.knowledge_point import KnowledgePoint
from app.auth_utils import require_teacher, require_authenticated, get_request_role, get_request_student_id
from app.services.ai_service import generate_quizzes_for_course

quizzes_bp = Blueprint("quizzes", __name__)


def _quiz_to_dict(quiz):
    data = quiz.to_dict()
    if data.get("video_timestamp") is None and quiz.knowledge_point_id:
        kp = db.session.get(KnowledgePoint, quiz.knowledge_point_id)
        if kp and kp.video_timestamp is not None:
            data["video_timestamp"] = kp.video_timestamp
    return data


@quizzes_bp.route("/generate/<int:course_id>", methods=["POST"])
def generate_quizzes(course_id):
    """Generate quiz questions for a course using AI (students and teachers)."""
    forbidden = require_authenticated()
    if forbidden:
        return forbidden

    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    data = request.get_json(silent=True) or {}
    num_questions = min(int(data.get("num_questions", 5)), 20)

    quiz_data_list = generate_quizzes_for_course(course_id, num_questions)

    if not quiz_data_list:
        return jsonify({
            "error": "No course content available. Please upload slides first.",
            "quizzes": [],
        }), 400

    created = []
    for qd in quiz_data_list:
        quiz = Quiz(
            course_id=course_id,
            knowledge_point_id=qd.get("knowledge_point_id"),
            question=qd.get("question", ""),
            options=qd.get("options", []),
            correct_answer=qd.get("correct_answer", "A"),
            explanation=qd.get("explanation", ""),
            video_timestamp=qd.get("video_timestamp"),
        )
        db.session.add(quiz)
        created.append(quiz)

    db.session.commit()
    return jsonify({
        "message": f"Generated {len(created)} quiz questions",
        "quizzes": [_quiz_to_dict(q) for q in created],
    }), 201


@quizzes_bp.route("/course/<int:course_id>", methods=["GET"])
def get_quizzes(course_id):
    """Get all quizzes for a course (public)."""
    quizzes = (
        Quiz.query.filter_by(course_id=course_id)
        .order_by(Quiz.created_at.desc())
        .all()
    )
    return jsonify([_quiz_to_dict(q) for q in quizzes])


@quizzes_bp.route("/<int:quiz_id>/attempt", methods=["POST"])
def submit_attempt(quiz_id):
    """Submit an answer for a quiz question (student and public)."""
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404

    data = request.get_json()
    if not data or not data.get("selected_answer"):
        return jsonify({"error": "selected_answer is required"}), 400

    selected = data["selected_answer"]
    is_correct = selected.upper() == quiz.correct_answer.upper()

    # Track student ID if available
    student_id = get_request_student_id() if get_request_role() == "student" else None

    attempt = QuizAttempt(
        quiz_id=quiz_id,
        selected_answer=selected,
        is_correct=is_correct,
    )
    db.session.add(attempt)
    db.session.commit()

    return jsonify({
        "attempt": attempt.to_dict(),
        "is_correct": is_correct,
        "correct_answer": quiz.correct_answer,
        "explanation": quiz.explanation,
        "video_timestamp": quiz.video_timestamp,
    }), 201


@quizzes_bp.route("/<int:quiz_id>", methods=["DELETE"])
def delete_quiz(quiz_id):
    """Delete a single quiz question (teacher only)."""
    forbidden = require_teacher()
    if forbidden:
        return forbidden

    quiz = db.session.get(Quiz, quiz_id)
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404
    db.session.delete(quiz)
    db.session.commit()
    return jsonify({"message": "Quiz deleted"})


@quizzes_bp.route("/course/<int:course_id>", methods=["DELETE"])
def clear_quizzes(course_id):
    """Delete all quizzes for a course (teacher only)."""
    forbidden = require_teacher()
    if forbidden:
        return forbidden

    quizzes = Quiz.query.filter_by(course_id=course_id).all()
    for q in quizzes:
        db.session.delete(q)  # triggers cascade delete of QuizAttempts
    db.session.commit()
    return jsonify({"message": "All quizzes cleared"})


@quizzes_bp.route("/stats/<int:course_id>", methods=["GET"])
def quiz_stats(course_id):
    """Get quiz performance statistics for a course (teacher only, for dashboard)."""
    forbidden = require_teacher()
    if forbidden:
        return forbidden

    quizzes = Quiz.query.filter_by(course_id=course_id).all()
    if not quizzes:
        return jsonify({"total_quizzes": 0, "questions": []})

    questions = []
    total_attempts = 0
    total_correct = 0
    for q in quizzes:
        attempts = QuizAttempt.query.filter_by(quiz_id=q.id).all()
        correct = sum(1 for a in attempts if a.is_correct)
        total_attempts += len(attempts)
        total_correct += correct
        error_rate = round(1 - correct / len(attempts), 3) if attempts else 0
        questions.append({
            "quiz_id": q.id,
            "question": q.question,
            "knowledge_point_id": q.knowledge_point_id,
            "video_timestamp": _quiz_to_dict(q).get("video_timestamp"),
            "attempts": len(attempts),
            "correct": correct,
            "error_rate": error_rate,
        })

    # Sort by error rate descending (highest error first)
    questions.sort(key=lambda x: x["error_rate"], reverse=True)

    return jsonify({
        "total_quizzes": len(quizzes),
        "total_attempts": total_attempts,
        "overall_accuracy": round(total_correct / total_attempts, 3) if total_attempts else 0,
        "questions": questions,
    })
