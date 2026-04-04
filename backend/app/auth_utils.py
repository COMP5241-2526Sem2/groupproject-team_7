from flask import request, jsonify


def get_request_role() -> str:
    """Get the user role from request headers. Returns: 'teacher', 'student', or 'anonymous'."""
    role = (request.headers.get("X-User-Role") or "").strip().lower()
    if role in ("teacher", "student"):
        return role
    return "anonymous"


def get_request_student_id() -> str:
    """Get the student ID from request headers."""
    return (request.headers.get("X-Student-Id") or "").strip()


def require_teacher():
    """Decorator/check: ensure user has teacher role."""
    role = get_request_role()
    if role != "teacher":
        return jsonify({"error": "Forbidden: teacher role required"}), 403
    return None


def require_student():
    """Decorator/check: ensure user has student role."""
    role = get_request_role()
    if role != "student":
        return jsonify({"error": "Forbidden: student role required"}), 403
    student_id = get_request_student_id()
    if not student_id:
        return jsonify({"error": "Forbidden: student ID required"}), 403
    return None


def require_authenticated():
    """Decorator/check: ensure user is authenticated (teacher or student)."""
    role = get_request_role()
    if role not in ("teacher", "student"):
        return jsonify({"error": "Forbidden: authentication required"}), 403
    return None
