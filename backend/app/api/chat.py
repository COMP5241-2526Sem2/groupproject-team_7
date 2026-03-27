from flask import Blueprint, request, jsonify
from app.services.ai_service import generate_chat_response
from app.services.supabase_repo import (
    select_rows,
    select_one_by_id,
    insert_row,
    delete_rows_by_eq,
    serialize_chat_message,
)

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/<int:course_id>", methods=["GET"])
def get_chat_history(course_id):
    messages = select_rows(
        "chat_messages",
        filters=[("eq", "course_id", course_id)],
        order_by="created_at",
        ascending=True,
    )
    return jsonify([serialize_chat_message(m) for m in messages])


@chat_bp.route("/<int:course_id>", methods=["POST"])
def send_message(course_id):
    course = select_one_by_id("courses", course_id, columns="id")
    if not course:
        return jsonify({"error": "Course not found"}), 404

    data = request.get_json()
    if not data or not data.get("content"):
        return jsonify({"error": "Message content is required"}), 400

    # Save user message
    user_msg = insert_row(
        "chat_messages",
        {
            "course_id": course_id,
            "role": "user",
            "content": data["content"],
            "citations": [],
        },
    )

    # Get recent history for context
    history = select_rows(
        "chat_messages",
        filters=[("eq", "course_id", course_id)],
        order_by="created_at",
        ascending=True,
    )

    # Generate AI response using OpenAI with slide content as context
    ai_response = generate_chat_response(course_id, data["content"], history)
    assistant_msg = insert_row(
        "chat_messages",
        {
            "course_id": course_id,
            "role": "assistant",
            "content": ai_response["content"],
            "citations": ai_response.get("citations", []),
        },
    )

    return jsonify({
        "user_message": serialize_chat_message(user_msg),
        "assistant_message": serialize_chat_message(assistant_msg),
    }), 201


@chat_bp.route("/<int:course_id>", methods=["DELETE"])
def clear_chat(course_id):
    delete_rows_by_eq("chat_messages", "course_id", course_id)
    return jsonify({"message": "Chat history cleared"})
