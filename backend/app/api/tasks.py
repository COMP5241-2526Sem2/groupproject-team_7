"""
Task Queue API endpoints.

Provides REST API for managing async tasks using Upstash Redis.
"""

from flask import Blueprint, request, jsonify
from ..services.redis_service import redis_service, TaskStatus

bp = Blueprint("tasks", __name__, url_prefix="/tasks")


@bp.route("/health", methods=["GET"])
def health_check():
    """Check if Redis task queue is available."""
    return jsonify({
        "status": "ok",
        "redis_available": redis_service.is_available
    })


@bp.route("/enqueue", methods=["POST"])
def enqueue_task():
    """
    Add a new task to the queue.
    
    Request body:
    {
        "queue": "video_processing",
        "type": "transcode",
        "payload": {...},
        "priority": 0  # optional, higher = more important
    }
    """
    if not redis_service.is_available:
        return jsonify({"error": "Task queue not available"}), 503
    
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    queue_name = data.get("queue")
    task_type = data.get("type")
    payload = data.get("payload", {})
    priority = data.get("priority", 0)
    
    if not queue_name or not task_type:
        return jsonify({"error": "queue and type are required"}), 400
    
    task_id = redis_service.enqueue_task(
        queue_name=queue_name,
        task_type=task_type,
        payload=payload,
        priority=priority
    )
    
    if task_id:
        return jsonify({
            "success": True,
            "task_id": task_id,
            "message": f"Task enqueued to {queue_name}"
        }), 201
    else:
        return jsonify({"error": "Failed to enqueue task"}), 500


@bp.route("/<task_id>", methods=["GET"])
def get_task(task_id):
    """Get task status and details by ID."""
    if not redis_service.is_available:
        return jsonify({"error": "Task queue not available"}), 503
    
    task = redis_service.get_task(task_id)
    
    if task:
        return jsonify(task)
    else:
        return jsonify({"error": "Task not found"}), 404


@bp.route("/<task_id>/status", methods=["PUT"])
def update_task(task_id):
    """
    Update task status.
    
    Request body:
    {
        "status": "completed",  # pending, processing, completed, failed
        "result": {...},  # optional
        "error": "..."  # optional, for failed tasks
    }
    """
    if not redis_service.is_available:
        return jsonify({"error": "Task queue not available"}), 503
    
    data = request.get_json()
    
    if not data or "status" not in data:
        return jsonify({"error": "status is required"}), 400
    
    try:
        status = TaskStatus(data["status"])
    except ValueError:
        return jsonify({
            "error": f"Invalid status. Must be one of: {[s.value for s in TaskStatus]}"
        }), 400
    
    success = redis_service.update_task_status(
        task_id=task_id,
        status=status,
        result=data.get("result"),
        error=data.get("error")
    )
    
    if success:
        return jsonify({"success": True, "message": "Task status updated"})
    else:
        return jsonify({"error": "Failed to update task"}), 500


@bp.route("/queue/<queue_name>/next", methods=["POST"])
def dequeue_task(queue_name):
    """Get and process the next task from a queue."""
    if not redis_service.is_available:
        return jsonify({"error": "Task queue not available"}), 503
    
    task = redis_service.dequeue_task(queue_name)
    
    if task:
        return jsonify(task)
    else:
        return jsonify({"message": "No tasks in queue"}), 204


@bp.route("/queue/<queue_name>/length", methods=["GET"])
def queue_length(queue_name):
    """Get the number of pending tasks in a queue."""
    if not redis_service.is_available:
        return jsonify({"error": "Task queue not available"}), 503
    
    length = redis_service.get_queue_length(queue_name)
    
    return jsonify({
        "queue": queue_name,
        "length": length
    })
