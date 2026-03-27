import json
import logging

from flask import current_app
from openai import OpenAI

from app import db
from app.models.slide import Slide
from app.models.knowledge_point import KnowledgePoint
from app.models.chat import ChatMessage

logger = logging.getLogger(__name__)


def _get_client():
    """Get OpenAI-compatible client (works with OpenAI and GitHub Models)."""
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    base_url = current_app.config.get("OPENAI_BASE_URL", "") or None
    return OpenAI(api_key=api_key, base_url=base_url)


def _chat_model():
    return current_app.config.get("OPENAI_CHAT_MODEL", "openai/gpt-4.1")


def _gather_course_context(course_id, max_chars=12000):
    """Gather all slide text and video transcript content for a course as RAG context."""
    slides = (
        Slide.query.filter_by(course_id=course_id)
        .order_by(Slide.created_at.asc())
        .all()
    )
    parts = []
    total = 0

    # Slide content
    for slide in slides:
        for page in sorted(slide.pages, key=lambda p: p.page_number):
            text = (page.content_text or "").strip()
            if not text:
                continue
            entry = f"[{slide.original_filename}, Page {page.page_number}]\n{text}"
            if total + len(entry) > max_chars * 0.7:
                parts.append("...(remaining slide content truncated)")
                break
            parts.append(entry)
            total += len(entry)

    # Video transcript content
    from app.models.video import Video
    from app.models.video_transcript import VideoTranscript

    videos = Video.query.filter_by(course_id=course_id).order_by(Video.created_at.asc()).all()
    for video in videos:
        segments = (
            VideoTranscript.query
            .filter_by(video_id=video.id)
            .order_by(VideoTranscript.start_time)
            .all()
        )
        if not segments:
            continue

        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue
            minutes = int(seg.start_time // 60)
            seconds = int(seg.start_time % 60)
            entry = f"[{video.original_filename}, {minutes}:{seconds:02d}]\n{text}"
            if total + len(entry) > max_chars:
                parts.append("...(remaining transcript content truncated)")
                break
            parts.append(entry)
            total += len(entry)

    return "\n\n---\n\n".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# 1. Chat — RAG-style response using slide content
# ---------------------------------------------------------------------------

def generate_chat_response(course_id, user_message, chat_history):
    """Generate AI chat response using course slide content as context."""
    client = _get_client()
    if client is None:
        return _fallback_chat_response(user_message)

    context = _gather_course_context(course_id)
    if not context:
        context = "(No slides have been uploaded yet.)"

    system_prompt = (
        "You are an AI teaching assistant for an online course. "
        "Answer students' questions based on the course materials below.\n\n"
        "Course Materials:\n"
        f"{context}\n\n"
        "Guidelines:\n"
        "- Provide clear, educational answers based on the materials.\n"
        "- When referencing slide content, cite as [filename, Page X].\n"
        "- When referencing video content, cite as [filename, M:SS].\n"
        "- If a question is outside the course scope, say so politely.\n"
        "- Keep answers concise but thorough.\n"
        "- Use the same language as the student's question."
    )

    messages = [{"role": "system", "content": system_prompt}]
    # Include recent chat history for conversation context
    for msg in chat_history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model=_chat_model(),
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )
        content = response.choices[0].message.content
        citations = _parse_citations(content)
        return {"content": content, "citations": citations}
    except Exception as e:
        logger.error("OpenAI chat error: %s", e)
        return {
            "content": f"Sorry, I encountered an error processing your question. Please try again. (Error: {type(e).__name__})",
            "citations": [],
        }


def _parse_citations(text):
    """Extract [filename, Page X] and [filename, M:SS] references from AI response."""
    import re
    citations = []
    # Slide citations: [filename, Page X]
    slide_pattern = r'\[([^,\]]+),\s*Page\s*(\d+)\]'
    for match in re.finditer(slide_pattern, text):
        citations.append({
            "type": "slide",
            "source": match.group(1).strip(),
            "page": int(match.group(2)),
            "label": f"{match.group(1).strip()}, Page {match.group(2)}",
        })
    # Video citations: [filename, M:SS] or [filename, MM:SS]
    video_pattern = r'\[([^,\]]+),\s*(\d+):(\d{2})\]'
    for match in re.finditer(video_pattern, text):
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        timestamp = minutes * 60 + seconds
        citations.append({
            "type": "video",
            "source": match.group(1).strip(),
            "timestamp": timestamp,
            "label": f"{match.group(1).strip()}, {match.group(2)}:{match.group(3)}",
        })
    return citations


def _fallback_chat_response(user_message):
    """Fallback when OpenAI API key is not configured."""
    return {
        "content": (
            "⚠️ OpenAI API key is not configured. To enable AI-powered answers:\n\n"
            "1. Set the `OPENAI_API_KEY` environment variable\n"
            "2. Restart the backend service\n\n"
            "Once configured, I'll be able to answer questions about your course materials "
            "with precise citations from your slides."
        ),
        "citations": [],
    }


# ---------------------------------------------------------------------------
# 2. Knowledge Point Extraction
# ---------------------------------------------------------------------------

def extract_knowledge_points_from_page(slide_page):
    """Use AI to extract knowledge points from a slide page."""
    client = _get_client()
    text = (slide_page.content_text or "").strip()

    if not text:
        return []

    if client is None:
        return _fallback_extract_kp(text)

    prompt = (
        "Extract key knowledge points from this slide content.\n"
        "Return a JSON array (no markdown, no extra text):\n"
        '[{"title": "short title (max 50 chars)", "content": "brief explanation (1-2 sentences)"}]\n'
        "Extract 2-5 knowledge points. Only return valid JSON.\n\n"
        f"Slide content:\n{text[:3000]}"
    )

    try:
        response = client.chat.completions.create(
            model=_chat_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        return _parse_json_response(response.choices[0].message.content)
    except Exception as e:
        logger.error("OpenAI KP extraction error: %s", e)
        return _fallback_extract_kp(text)


def _fallback_extract_kp(text):
    """Simple fallback: create a single KP from first sentence."""
    sentences = [s.strip() for s in text.replace("\n", ". ").split(". ") if len(s.strip()) > 10]
    results = []
    for s in sentences[:3]:
        title = s[:50] + ("..." if len(s) > 50 else "")
        results.append({"title": title, "content": s[:200]})
    return results if results else [{"title": "Key Concept", "content": text[:200]}]


# ---------------------------------------------------------------------------
# 3. Quiz Generation — linked to knowledge points
# ---------------------------------------------------------------------------

def generate_quizzes_for_course(course_id, num_questions=5):
    """Use AI to generate quiz questions linked to knowledge points."""
    client = _get_client()
    context = _gather_course_context(course_id, max_chars=8000)

    if not context:
        return []

    # Gather knowledge points for linking
    from app.models.slide import Slide
    from app.models.knowledge_point import KnowledgePoint

    slides = Slide.query.filter_by(course_id=course_id).all()
    page_ids = []
    for s in slides:
        page_ids.extend([p.id for p in s.pages])

    kp_list = []
    if page_ids:
        kps = KnowledgePoint.query.filter(
            KnowledgePoint.slide_page_id.in_(page_ids)
        ).all()
        kp_list = [
            {"id": kp.id, "title": kp.title, "content": kp.content,
             "video_timestamp": kp.video_timestamp}
            for kp in kps
        ]

    if client is None:
        return _fallback_generate_quiz(context, num_questions, kp_list)

    # Build KP reference for the prompt
    kp_ref = ""
    if kp_list:
        kp_entries = [f"  KP#{kp['id']}: {kp['title']}" for kp in kp_list[:30]]
        kp_ref = (
            "\n\nAvailable Knowledge Points (use these IDs in knowledge_point_id):\n"
            + "\n".join(kp_entries)
        )

    prompt = (
        f"Generate {num_questions} multiple choice quiz questions based on this course content.\n"
        "Return a JSON array (no markdown, no extra text):\n"
        '[{"question": "...", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], '
        '"correct_answer": "A", "explanation": "brief explanation", '
        '"knowledge_point_id": <integer KP ID or null>}]\n'
        "Link each question to the most relevant knowledge point ID if possible.\n"
        "Only return valid JSON.\n\n"
        f"Course content:\n{context}"
        f"{kp_ref}"
    )

    try:
        response = client.chat.completions.create(
            model=_chat_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=2000,
        )
        results = _parse_json_response(response.choices[0].message.content)

        # Attach video timestamps from linked KPs
        kp_map = {kp["id"]: kp for kp in kp_list}
        for item in results:
            kp_id = item.get("knowledge_point_id")
            if kp_id and kp_id in kp_map:
                item["video_timestamp"] = kp_map[kp_id].get("video_timestamp")
            else:
                item["knowledge_point_id"] = None
                item["video_timestamp"] = None

        return results
    except Exception as e:
        logger.error("OpenAI quiz generation error: %s", e)
        return _fallback_generate_quiz(context, num_questions, kp_list)


def _fallback_generate_quiz(context, num_questions, kp_list=None):
    """Fallback quiz when no API key — generate content-based questions from slides."""
    import re
    # Extract meaningful sentences from context
    sentences = []
    for line in context.split("\n"):
        line = line.strip()
        if not line or line.startswith("[") or line.startswith("---") or line.startswith("..."):
            continue
        for s in re.split(r'[.;。；]', line):
            s = s.strip()
            if len(s) > 20:
                sentences.append(s)

    quizzes = []
    for i in range(min(num_questions, max(len(sentences), 1))):
        if i < len(sentences):
            topic = sentences[i][:100]
            q_text = f"Which of the following best describes this concept: \"{topic}\"?"
        else:
            q_text = f"Question {i+1}: What is covered in the course materials?"

        kp = kp_list[i % len(kp_list)] if kp_list else None
        quizzes.append({
            "question": q_text,
            "options": [
                "A. " + (sentences[i][:80] if i < len(sentences) else "The content from the uploaded materials"),
                "B. An unrelated concept not covered in the course",
                "C. A topic from a different subject area",
                "D. None of the above descriptions apply",
            ],
            "correct_answer": "A",
            "explanation": "This is based on the uploaded course content. Connect an OpenAI API key for better AI-generated quizzes.",
            "knowledge_point_id": kp["id"] if kp else None,
            "video_timestamp": kp.get("video_timestamp") if kp else None,
        })

    return quizzes if quizzes else [{
        "question": "What is the main topic covered in the uploaded slides?",
        "options": [
            "A. The content from the uploaded course materials",
            "B. An unrelated subject",
            "C. General knowledge",
            "D. None of the above",
        ],
        "correct_answer": "A",
        "explanation": "Upload slides and configure an OpenAI API key for AI-generated quizzes.",
        "knowledge_point_id": None,
        "video_timestamp": None,
    }]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_response(text):
    """Parse JSON from an LLM response, handling markdown code blocks."""
    text = text.strip()
    # Remove markdown code fences
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            cleaned = part.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            if cleaned.startswith("["):
                text = cleaned
                break
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find array in text
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        logger.warning("Failed to parse JSON from LLM response: %s", text[:200])
        return []
