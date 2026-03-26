from flask import Blueprint, request, jsonify
from app import db
from app.models.chat import ChatMessage
from app.models.course import Course
from app.services.ai_service import generate_chat_response

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/<int:course_id>", methods=["GET"])
def get_chat_history(course_id):
    messages = (
        ChatMessage.query.filter_by(course_id=course_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return jsonify([m.to_dict() for m in messages])


@chat_bp.route("/<int:course_id>", methods=["POST"])
def send_message(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    data = request.get_json()
    if not data or not data.get("content"):
        return jsonify({"error": "Message content is required"}), 400

    # Save user message
    user_msg = ChatMessage(
        course_id=course_id,
        role="user",
        content=data["content"],
    )
    db.session.add(user_msg)

    # Get recent history for context
    history = (
        ChatMessage.query.filter_by(course_id=course_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    # Generate AI response using OpenAI with slide content as context
    ai_response = generate_chat_response(course_id, data["content"], history)
    assistant_msg = ChatMessage(
        course_id=course_id,
        role="assistant",
        content=ai_response["content"],
        citations=ai_response.get("citations", []),
    )
    db.session.add(assistant_msg)
    db.session.commit()

    return jsonify({
        "user_message": user_msg.to_dict(),
        "assistant_message": assistant_msg.to_dict(),
    }), 201


@chat_bp.route("/<int:course_id>", methods=["DELETE"])
def clear_chat(course_id):
    ChatMessage.query.filter_by(course_id=course_id).delete()
    db.session.commit()
    return jsonify({"message": "Chat history cleared"})
