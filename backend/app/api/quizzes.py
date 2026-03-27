from flask import Blueprint, request, jsonify
from app.services.ai_service import generate_quizzes_for_course
from app.services.supabase_repo import (
    select_rows,
    select_one_by_id,
    insert_row,
    delete_row_by_id,
    serialize_quiz,
    serialize_quiz_attempt,
)

quizzes_bp = Blueprint("quizzes", __name__)


@quizzes_bp.route("/generate/<int:course_id>", methods=["POST"])
def generate_quizzes(course_id):
    """Generate quiz questions for a course using AI."""
    course = select_one_by_id("courses", course_id, columns="id")
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
        quiz = insert_row(
            "quizzes",
            {
                "course_id": course_id,
                "knowledge_point_id": qd.get("knowledge_point_id"),
                "question": qd.get("question", ""),
                "options": qd.get("options", []),
                "correct_answer": qd.get("correct_answer", "A"),
                "explanation": qd.get("explanation", ""),
                "video_timestamp": qd.get("video_timestamp"),
            },
        )
        created.append(quiz)

    return jsonify({
        "message": f"Generated {len(created)} quiz questions",
        "quizzes": [serialize_quiz(q) for q in created],
    }), 201


@quizzes_bp.route("/course/<int:course_id>", methods=["GET"])
def get_quizzes(course_id):
    """Get all quizzes for a course."""
    quizzes = select_rows(
        "quizzes",
        filters=[("eq", "course_id", course_id)],
        order_by="created_at",
        ascending=False,
    )
    return jsonify([serialize_quiz(q) for q in quizzes])


@quizzes_bp.route("/<int:quiz_id>/attempt", methods=["POST"])
def submit_attempt(quiz_id):
    """Submit an answer for a quiz question."""
    quiz = select_one_by_id("quizzes", quiz_id)
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404

    data = request.get_json()
    if not data or not data.get("selected_answer"):
        return jsonify({"error": "selected_answer is required"}), 400

    selected = data["selected_answer"]
    is_correct = selected.upper() == (quiz.get("correct_answer") or "").upper()

    attempt = insert_row(
        "quiz_attempts",
        {
            "quiz_id": quiz_id,
            "selected_answer": selected,
            "is_correct": is_correct,
        },
    )

    return jsonify({
        "attempt": serialize_quiz_attempt(attempt),
        "is_correct": is_correct,
        "correct_answer": quiz.get("correct_answer"),
        "explanation": quiz.get("explanation"),
    }), 201


@quizzes_bp.route("/<int:quiz_id>", methods=["DELETE"])
def delete_quiz(quiz_id):
    quiz = select_one_by_id("quizzes", quiz_id, columns="id")
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404
    delete_row_by_id("quizzes", quiz_id)
    return jsonify({"message": "Quiz deleted"})


@quizzes_bp.route("/course/<int:course_id>", methods=["DELETE"])
def clear_quizzes(course_id):
    """Delete all quizzes for a course."""
    quizzes = select_rows("quizzes", columns="id", filters=[("eq", "course_id", course_id)])
    for q in quizzes:
        delete_row_by_id("quizzes", q["id"])
    return jsonify({"message": "All quizzes cleared"})


@quizzes_bp.route("/stats/<int:course_id>", methods=["GET"])
def quiz_stats(course_id):
    """Get quiz performance statistics for a course (for teacher dashboard)."""
    quizzes = select_rows("quizzes", filters=[("eq", "course_id", course_id)])
    if not quizzes:
        return jsonify({"total_quizzes": 0, "questions": []})

    questions = []
    total_attempts = 0
    total_correct = 0
    for q in quizzes:
        attempts = select_rows("quiz_attempts", filters=[("eq", "quiz_id", q["id"])])
        correct = sum(1 for a in attempts if a.get("is_correct"))
        total_attempts += len(attempts)
        total_correct += correct
        error_rate = round(1 - correct / len(attempts), 3) if attempts else 0
        questions.append({
            "quiz_id": q.get("id"),
            "question": q.get("question"),
            "knowledge_point_id": q.get("knowledge_point_id"),
            "video_timestamp": q.get("video_timestamp"),
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
