from flask import Blueprint, jsonify, current_app

from app.services.supabase_repo import select_rows, select_one_by_id


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/summary/<int:course_id>", methods=["GET"])
def course_summary(course_id):
    """Get overall course statistics for the teacher dashboard."""
    course = select_one_by_id("courses", course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    slides = select_rows("slides", columns="id", filters=[("eq", "course_id", course_id)])
    videos = select_rows("videos", columns="id", filters=[("eq", "course_id", course_id)])

    page_ids = []
    for slide in slides:
        pages = select_rows("slide_pages", columns="id", filters=[("eq", "slide_id", slide["id"])])
        page_ids.extend([p["id"] for p in pages])

    kp_count = len(select_rows("knowledge_points", columns="id", filters=[("in", "slide_page_id", page_ids)])) if page_ids else 0

    quizzes = select_rows("quizzes", filters=[("eq", "course_id", course_id)])
    total_attempts = 0
    total_correct = 0
    for quiz in quizzes:
        attempts = select_rows("quiz_attempts", filters=[("eq", "quiz_id", quiz["id"])])
        total_attempts += len(attempts)
        total_correct += sum(1 for attempt in attempts if attempt.get("is_correct"))

    chat_count = len(select_rows("chat_messages", columns="id", filters=[("eq", "course_id", course_id), ("eq", "role", "user")]))

    return jsonify(
        {
            "course_id": course_id,
            "course_title": course.get("title"),
            "slides_count": len(slides),
            "videos_count": len(videos),
            "knowledge_points_count": kp_count,
            "quizzes_count": len(quizzes),
            "total_quiz_attempts": total_attempts,
            "quiz_accuracy": round(total_correct / total_attempts, 3) if total_attempts else 0,
            "chat_questions_count": chat_count,
        }
    )


@dashboard_bp.route("/difficulty/<int:course_id>", methods=["GET"])
def difficulty_analysis(course_id):
    """Get top difficult knowledge points based on quiz error rates."""
    quizzes = select_rows("quizzes", filters=[("eq", "course_id", course_id)])
    if not quizzes:
        return jsonify({"difficulties": []})

    kp_errors = {}
    unlinked_errors = []

    for quiz in quizzes:
        attempts = select_rows("quiz_attempts", filters=[("eq", "quiz_id", quiz["id"])])
        if not attempts:
            continue
        errors = sum(1 for attempt in attempts if not attempt.get("is_correct"))
        error_rate = errors / len(attempts) if attempts else 0

        knowledge_point_id = quiz.get("knowledge_point_id")
        if knowledge_point_id:
            if knowledge_point_id not in kp_errors:
                kp = select_one_by_id("knowledge_points", knowledge_point_id)
                kp_errors[knowledge_point_id] = {
                    "knowledge_point_id": knowledge_point_id,
                    "title": kp.get("title") if kp else "Unknown",
                    "video_timestamp": kp.get("video_timestamp") if kp else None,
                    "total_attempts": 0,
                    "total_errors": 0,
                    "questions": [],
                }
            entry = kp_errors[knowledge_point_id]
            entry["total_attempts"] += len(attempts)
            entry["total_errors"] += errors
            entry["questions"].append({"question": quiz.get("question"), "error_rate": round(error_rate, 3)})
        else:
            unlinked_errors.append(
                {
                    "question": quiz.get("question"),
                    "attempts": len(attempts),
                    "error_rate": round(error_rate, 3),
                    "video_timestamp": quiz.get("video_timestamp"),
                }
            )

    difficulties = []
    for _, entry in kp_errors.items():
        entry["error_rate"] = round(entry["total_errors"] / entry["total_attempts"], 3) if entry["total_attempts"] else 0
        difficulties.append(entry)

    difficulties.sort(key=lambda x: x["error_rate"], reverse=True)

    return jsonify({"difficulties": difficulties[:10], "unlinked_questions": unlinked_errors})


@dashboard_bp.route("/chat-insights/<int:course_id>", methods=["GET"])
def chat_insights(course_id):
    """Analyze student chat questions to identify common topics and concerns."""
    messages = select_rows(
        "chat_messages",
        filters=[("eq", "course_id", course_id), ("eq", "role", "user")],
        order_by="created_at",
        ascending=False,
        limit=100,
    )

    if not messages:
        return jsonify({"total_questions": 0, "recent_questions": []})

    recent = []
    for message in messages[:20]:
        created_at = message.get("created_at")
        recent.append(
            {
                "content": (message.get("content") or "")[:200],
                "created_at": str(created_at) if created_at else None,
            }
        )

    return jsonify({"total_questions": len(messages), "recent_questions": recent})


@dashboard_bp.route("/review-brief/<int:course_id>", methods=["POST"])
def generate_review_brief(course_id):
    """Generate an AI-powered review brief summarizing learning gaps."""
    course = select_one_by_id("courses", course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    from app.services.ai_service import _get_client

    client = _get_client()
    if client is None:
        return jsonify({"error": "OpenAI API key not configured"}), 400

    quizzes = select_rows("quizzes", filters=[("eq", "course_id", course_id)])
    quiz_summary = []
    for quiz in quizzes:
        attempts = select_rows("quiz_attempts", filters=[("eq", "quiz_id", quiz["id"])])
        if attempts:
            errors = sum(1 for attempt in attempts if not attempt.get("is_correct"))
            quiz_summary.append(f"Q: {quiz.get('question')} - Error rate: {errors}/{len(attempts)}")

    messages = select_rows(
        "chat_messages",
        filters=[("eq", "course_id", course_id), ("eq", "role", "user")],
        order_by="created_at",
        ascending=False,
        limit=30,
    )
    questions = [(message.get("content") or "")[:150] for message in messages]

    slides = select_rows("slides", columns="id", filters=[("eq", "course_id", course_id)])
    page_ids = []
    for slide in slides:
        pages = select_rows("slide_pages", columns="id", filters=[("eq", "slide_id", slide["id"])])
        page_ids.extend([p["id"] for p in pages])

    knowledge_points = select_rows("knowledge_points", filters=[("in", "slide_page_id", page_ids)]) if page_ids else []
    kp_titles = [kp.get("title") for kp in knowledge_points]

    context = (
        f"Course: {course.get('title')}\n\n"
        f"Knowledge Points ({len(kp_titles)}):\n"
        + "\n".join(f"- {title}" for title in kp_titles[:20])
        + "\n\n"
        f"Quiz Results ({len(quiz_summary)} questions with attempts):\n"
        + "\n".join(quiz_summary[:15])
        + "\n\n"
        f"Student Questions ({len(questions)} recent):\n"
        + "\n".join(f"- {question}" for question in questions[:15])
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
            model=current_app.config.get("OPENAI_CHAT_MODEL", "openai/gpt-4.1"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=1000,
        )
        brief = response.choices[0].message.content
        return jsonify({"brief": brief})
    except Exception as e:
        return jsonify({"error": f"Failed to generate brief: {e}"}), 500
