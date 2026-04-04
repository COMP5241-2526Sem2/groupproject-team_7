from flask import Blueprint, jsonify
from app import db
from app.models.course import Course
from app.models.quiz import Quiz, QuizAttempt
from app.models.knowledge_point import KnowledgePoint
from app.models.slide import Slide
from app.models.chat import ChatMessage
from app.auth_utils import require_teacher

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/summary/<int:course_id>", methods=["GET"])
def course_summary(course_id):
    """Get overall course statistics for the teacher dashboard."""
    forbidden = require_teacher()
    if forbidden:
        return forbidden

    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    # Count resources
    slides_count = len(course.slides)
    videos_count = len(course.videos)

    # Count knowledge points
    page_ids = []
    for s in course.slides:
        page_ids.extend([p.id for p in s.pages])
    kp_count = (
        KnowledgePoint.query.filter(KnowledgePoint.slide_page_id.in_(page_ids)).count()
        if page_ids else 0
    )

    # Quiz stats
    quizzes = Quiz.query.filter_by(course_id=course_id).all()
    total_attempts = 0
    total_correct = 0
    for q in quizzes:
        attempts = QuizAttempt.query.filter_by(quiz_id=q.id).all()
        total_attempts += len(attempts)
        total_correct += sum(1 for a in attempts if a.is_correct)

    # Chat stats
    chat_count = ChatMessage.query.filter_by(course_id=course_id, role="user").count()

    return jsonify({
        "course_id": course_id,
        "course_title": course.title,
        "slides_count": slides_count,
        "videos_count": videos_count,
        "knowledge_points_count": kp_count,
        "quizzes_count": len(quizzes),
        "total_quiz_attempts": total_attempts,
        "quiz_accuracy": round(total_correct / total_attempts, 3) if total_attempts else 0,
        "chat_questions_count": chat_count,
    })


@dashboard_bp.route("/difficulty/<int:course_id>", methods=["GET"])
def difficulty_analysis(course_id):
    """Get top difficult knowledge points based on quiz error rates."""
    forbidden = require_teacher()
    if forbidden:
        return forbidden

    quizzes = Quiz.query.filter_by(course_id=course_id).all()
    if not quizzes:
        return jsonify({"difficulties": []})

    # Build per-KP error rates
    kp_errors = {}  # kp_id -> {attempts, errors, question}
    unlinked_errors = []

    for q in quizzes:
        attempts = QuizAttempt.query.filter_by(quiz_id=q.id).all()
        if not attempts:
            continue
        errors = sum(1 for a in attempts if not a.is_correct)
        error_rate = errors / len(attempts) if attempts else 0

        if q.knowledge_point_id:
            if q.knowledge_point_id not in kp_errors:
                kp = db.session.get(KnowledgePoint, q.knowledge_point_id)
                kp_errors[q.knowledge_point_id] = {
                    "knowledge_point_id": q.knowledge_point_id,
                    "title": kp.title if kp else "Unknown",
                    "video_timestamp": kp.video_timestamp if kp else None,
                    "total_attempts": 0,
                    "total_errors": 0,
                    "questions": [],
                }
            entry = kp_errors[q.knowledge_point_id]
            entry["total_attempts"] += len(attempts)
            entry["total_errors"] += errors
            entry["questions"].append({
                "question": q.question,
                "error_rate": round(error_rate, 3),
            })
        else:
            unlinked_errors.append({
                "question": q.question,
                "attempts": len(attempts),
                "error_rate": round(error_rate, 3),
                "video_timestamp": q.video_timestamp,
            })

    # Calculate overall error rate per KP
    difficulties = []
    for kp_id, entry in kp_errors.items():
        entry["error_rate"] = (
            round(entry["total_errors"] / entry["total_attempts"], 3)
            if entry["total_attempts"] else 0
        )
        difficulties.append(entry)

    # Sort by error rate descending
    difficulties.sort(key=lambda x: x["error_rate"], reverse=True)

    return jsonify({
        "difficulties": difficulties[:10],
        "unlinked_questions": unlinked_errors,
    })


@dashboard_bp.route("/chat-insights/<int:course_id>", methods=["GET"])
def chat_insights(course_id):
    """Analyze student chat questions to identify common topics and concerns."""
    forbidden = require_teacher()
    if forbidden:
        return forbidden

    messages = (
        ChatMessage.query
        .filter_by(course_id=course_id, role="user")
        .order_by(ChatMessage.created_at.desc())
        .limit(100)
        .all()
    )

    if not messages:
        return jsonify({"total_questions": 0, "recent_questions": []})

    recent = [
        {
            "content": m.content[:200],
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages[:20]
    ]

    return jsonify({
        "total_questions": len(messages),
        "recent_questions": recent,
    })


@dashboard_bp.route("/review-brief/<int:course_id>", methods=["POST"])
def generate_review_brief(course_id):
    """Generate an AI-powered review brief summarizing learning gaps."""
    forbidden = require_teacher()
    if forbidden:
        return forbidden

    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    from app.services.ai_service import _get_client

    client = _get_client()
    if client is None:
        return jsonify({"error": "OpenAI API key not configured"}), 400

    # Gather data for the brief
    # 1. Quiz difficulty data
    quizzes = Quiz.query.filter_by(course_id=course_id).all()
    quiz_summary = []
    for q in quizzes:
        attempts = QuizAttempt.query.filter_by(quiz_id=q.id).all()
        if attempts:
            errors = sum(1 for a in attempts if not a.is_correct)
            quiz_summary.append(
                f"Q: {q.question} — Error rate: {errors}/{len(attempts)}"
            )

    # 2. Student questions
    messages = (
        ChatMessage.query
        .filter_by(course_id=course_id, role="user")
        .order_by(ChatMessage.created_at.desc())
        .limit(30)
        .all()
    )
    questions = [m.content[:150] for m in messages]

    # 3. Knowledge points
    page_ids = []
    for s in course.slides:
        page_ids.extend([p.id for p in s.pages])
    kps = (
        KnowledgePoint.query.filter(KnowledgePoint.slide_page_id.in_(page_ids)).all()
        if page_ids else []
    )
    kp_titles = [kp.title for kp in kps]

    context = (
        f"Course: {course.title}\n\n"
        f"Knowledge Points ({len(kp_titles)}):\n"
        + "\n".join(f"- {t}" for t in kp_titles[:20])
        + "\n\n"
        f"Quiz Results ({len(quiz_summary)} questions with attempts):\n"
        + "\n".join(quiz_summary[:15])
        + "\n\n"
        f"Student Questions ({len(questions)} recent):\n"
        + "\n".join(f"- {q}" for q in questions[:15])
    )

    prompt = (
        "You are a teaching assistant analyzing student learning data.\n"
        "Based on the data below, generate a concise review brief for the teacher.\n\n"
        "Include:\n"
        "1. **Top Difficulties**: Top 3-5 knowledge points with highest error rates\n"
        "2. **Common Questions**: Cluster student questions into 2-3 themes\n"
        "3. **Review Recommendations**: 3-5 specific suggestions for the review session\n\n"
        "Keep it concise and actionable. Use the same language as the course content.\n\n"
        f"Data:\n{context}"
    )

    try:
        response = client.chat.completions.create(
            model=current_app.config.get("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=1000,
        )
        brief = response.choices[0].message.content
        return jsonify({"brief": brief})
    except Exception as e:
        return jsonify({"error": f"Failed to generate brief: {e}"}), 500
