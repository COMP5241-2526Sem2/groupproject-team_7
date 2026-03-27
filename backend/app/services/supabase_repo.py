from datetime import datetime
from typing import Any

from flask import current_app


class SupabaseRepoError(RuntimeError):
    """Raised when a Supabase operation fails or when client is unavailable."""


# The helper methods in this module centralize Supabase CRUD patterns so API routes
# can focus on business logic while keeping payload shapes consistent.
def get_client():
    client = current_app.config.get("SUPABASE_CLIENT")
    if client is None:
        raise SupabaseRepoError("Supabase client is not configured")
    return client


def select_rows(
    table: str,
    columns: str = "*",
    filters: list[tuple[str, str, Any]] | None = None,
    order_by: str | None = None,
    ascending: bool = True,
    limit: int | None = None,
):
    query = get_client().table(table).select(columns)
    for operator, column, value in (filters or []):
        if operator == "eq":
            query = query.eq(column, value)
        elif operator == "in":
            query = query.in_(column, value)
        elif operator == "is":
            query = query.is_(column, "null" if value is None else value)
        elif operator == "not.is":
            query = query.not_.is_(column, "null" if value is None else value)
        else:
            raise SupabaseRepoError(f"Unsupported filter operator: {operator}")
    if order_by:
        query = query.order(order_by, desc=not ascending)
    if limit is not None:
        query = query.limit(limit)
    response = query.execute()
    return response.data or []


def select_one_by_id(table: str, row_id: int, columns: str = "*"):
    response = get_client().table(table).select(columns).eq("id", row_id).limit(1).execute()
    data = response.data or []
    return data[0] if data else None


def insert_row(table: str, payload: dict[str, Any]):
    response = get_client().table(table).insert(payload).execute()
    data = response.data or []
    if not data:
        raise SupabaseRepoError(f"Insert returned no row for table {table}")
    return data[0]


def update_row_by_id(table: str, row_id: int, payload: dict[str, Any]):
    response = get_client().table(table).update(payload).eq("id", row_id).execute()
    data = response.data or []
    return data[0] if data else None


def delete_row_by_id(table: str, row_id: int):
    response = get_client().table(table).delete().eq("id", row_id).execute()
    data = response.data or []
    return data[0] if data else None


def delete_rows_by_eq(table: str, column: str, value: Any):
    response = get_client().table(table).delete().eq(column, value).execute()
    return response.data or []


def update_rows_by_eq(table: str, column: str, value: Any, payload: dict[str, Any]):
    response = get_client().table(table).update(payload).eq(column, value).execute()
    return response.data or []


def bytea_to_hex(data: bytes | None):
    if data is None:
        return None
    return "\\x" + data.hex()


def hex_to_bytea(value: str | None):
    if not value:
        return None
    text = value[2:] if value.startswith("\\x") else value
    return bytes.fromhex(text)


def _iso(value: Any):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def serialize_course(course: dict[str, Any], slides_count: int = 0, videos_count: int = 0):
    return {
        "id": course.get("id"),
        "title": course.get("title"),
        "description": course.get("description", ""),
        "created_at": _iso(course.get("created_at")),
        "slides_count": slides_count,
        "videos_count": videos_count,
    }


def serialize_video(video: dict[str, Any]):
    return {
        "id": video.get("id"),
        "course_id": video.get("course_id"),
        "filename": video.get("filename"),
        "original_filename": video.get("original_filename"),
        "duration": video.get("duration", 0),
        "processed": video.get("processed", False),
        "created_at": _iso(video.get("created_at")),
    }


def serialize_chat_message(message: dict[str, Any]):
    return {
        "id": message.get("id"),
        "course_id": message.get("course_id"),
        "role": message.get("role"),
        "content": message.get("content"),
        "citations": message.get("citations") or [],
        "created_at": _iso(message.get("created_at")),
    }


def serialize_quiz(quiz: dict[str, Any]):
    return {
        "id": quiz.get("id"),
        "course_id": quiz.get("course_id"),
        "knowledge_point_id": quiz.get("knowledge_point_id"),
        "question": quiz.get("question", ""),
        "options": quiz.get("options") or [],
        "correct_answer": quiz.get("correct_answer", "A"),
        "explanation": quiz.get("explanation", ""),
        "video_timestamp": quiz.get("video_timestamp"),
    }


def serialize_quiz_attempt(attempt: dict[str, Any]):
    return {
        "id": attempt.get("id"),
        "quiz_id": attempt.get("quiz_id"),
        "selected_answer": attempt.get("selected_answer"),
        "is_correct": attempt.get("is_correct", False),
        "created_at": _iso(attempt.get("created_at")),
    }


def serialize_video_transcript(segment: dict[str, Any]):
    return {
        "id": segment.get("id"),
        "video_id": segment.get("video_id"),
        "segment_index": segment.get("segment_index"),
        "start_time": segment.get("start_time"),
        "end_time": segment.get("end_time"),
        "text": segment.get("text", ""),
    }


def serialize_knowledge_point(kp: dict[str, Any], slide_page: dict[str, Any] | None = None):
    return {
        "id": kp.get("id"),
        "slide_page_id": kp.get("slide_page_id"),
        "slide_id": slide_page.get("slide_id") if slide_page else None,
        "page_number": slide_page.get("page_number") if slide_page else None,
        "video_id": kp.get("video_id"),
        "title": kp.get("title", ""),
        "content": kp.get("content", ""),
        "video_timestamp": kp.get("video_timestamp"),
        "confidence": kp.get("confidence", 0.0),
    }


def serialize_slide_page(page: dict[str, Any], knowledge_points: list[dict[str, Any]] | None = None):
    return {
        "id": page.get("id"),
        "page_number": page.get("page_number"),
        "content_text": page.get("content_text", ""),
        "thumbnail_path": page.get("thumbnail_path", ""),
        "knowledge_points": knowledge_points or [],
    }


def serialize_slide(slide: dict[str, Any], pages: list[dict[str, Any]] | None = None):
    return {
        "id": slide.get("id"),
        "course_id": slide.get("course_id"),
        "filename": slide.get("filename"),
        "original_filename": slide.get("original_filename"),
        "file_type": slide.get("file_type"),
        "total_pages": slide.get("total_pages", 0),
        "processed": slide.get("processed", False),
        "created_at": _iso(slide.get("created_at")),
        "pages": pages or [],
    }


def get_slide_pages(slide_id: int):
    return select_rows(
        "slide_pages",
        filters=[("eq", "slide_id", slide_id)],
        order_by="page_number",
        ascending=True,
    )


def get_slide_payload(slide: dict[str, Any]):
    pages = []
    for page in get_slide_pages(slide["id"]):
        kps_rows = select_rows("knowledge_points", filters=[("eq", "slide_page_id", page["id"])])
        kps = [serialize_knowledge_point(kp, slide_page=page) for kp in kps_rows]
        pages.append(serialize_slide_page(page, kps))
    return serialize_slide(slide, pages)
