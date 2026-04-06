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
    return current_app.config.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")


def _gather_course_context(course_id, max_chars=12000):
    """Gather slide text and knowledge points with video timestamps as RAG context."""
    from app.models.video import Video
    
    slides = (
        Slide.query.filter_by(course_id=course_id)
        .order_by(Slide.created_at.asc())
        .all()
    )
    parts = []
    total = 0

    # Slide content with associated knowledge points and video timestamps
    for slide in slides:
        for page in sorted(slide.pages, key=lambda p: p.page_number):
            text = (page.content_text or "").strip()
            if not text:
                continue
            
            # Get knowledge points for this page with video timestamp info
            kps = KnowledgePoint.query.filter_by(slide_page_id=page.id).all()
            kp_refs = []
            for kp in kps:
                if kp.video_timestamp is not None and kp.video_id:
                    video = db.session.get(Video, kp.video_id)
                    if video:
                        # Format: "KnowledgePoint Title [Video: MM:SS]"
                        minutes = int(kp.video_timestamp) // 60
                        seconds = int(kp.video_timestamp) % 60
                        ts_str = f"{minutes:02d}:{seconds:02d}"
                        kp_refs.append(f"{kp.title} [Video: {ts_str}]")
            
            entry = f"[{slide.original_filename}, Page {page.page_number}]\n{text}"
            if kp_refs:
                entry += f"\nKey concepts: {', '.join(kp_refs)}"
            
            if total + len(entry) > max_chars * 0.7:
                parts.append("...(remaining slide content truncated)")
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
        "- When referencing a concept with a video explanation, include [Video: MM:SS] in your answer.\n"
        "- For example: 'This concept is explained at [Video: 05:30]' or 'See [filename, Page X] and [Video: 02:15] for more details.'\n"
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
    """Extract [filename, Page X] and [Video: MM:SS] / [Video: HH:MM:SS] references from AI response."""
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
    
    # Video timestamp citations: [Video: MM:SS] or [Video: HH:MM:SS]
    video_pattern = r'\[Video:\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\]'
    for match in re.finditer(video_pattern, text):
        if match.group(3):  # HH:MM:SS format
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = int(match.group(3))
            timestamp = hours * 3600 + minutes * 60 + seconds
            label = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:  # MM:SS format
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            timestamp = minutes * 60 + seconds
            label = f"{minutes:02d}:{seconds:02d}"
        
        citations.append({
            "type": "video",
            "timestamp": timestamp,
            "label": label,
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


def extract_knowledge_points_from_pages(slide_pages):
    """Batch extract knowledge points from multiple pages (MUCH FASTER).
    
    Args:
        slide_pages: List of SlidePage objects
        
    Returns:
        Dict mapping page_id -> list of KP dicts
    """
    if not slide_pages:
        return {}
    
    client = _get_client()
    if client is None:
        # Fallback: process individually
        return {page.id: _fallback_extract_kp((page.content_text or "").strip()) 
                for page in slide_pages}
    
    # Prepare batch content - limit to most important content
    pages_content = []
    page_id_map = {}  # internal_idx -> page_id
    
    for idx, page in enumerate(slide_pages):
        text = (page.content_text or "").strip()
        if text:
            # Aggressive text truncation to speed up API
            # Take only first 1500 chars to reduce token usage and API time
            text = text[:1500]
            pages_content.append({
                "index": idx,
                "page_number": page.page_number,
                "content": text
            })
            page_id_map[idx] = page.id
    
    if not pages_content:
        return {page.id: [] for page in slide_pages}
    
    # Batch prompt - simplified for speed
    prompt = (
        "Extract 3-4 key knowledge points from each slide.\n"
        "Response format: {\"0\": [{\"title\": \"...\", \"content\": \"...\"}], ...}\n"
        "Be concise. Return ONLY valid JSON.\n\n"
    )
    
    for item in pages_content:
        prompt += f"[Page {item['page_number']}]:\n{item['content']}\n\n"
    
    try:
        response = client.chat.completions.create(
            model=_chat_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,  # Lower temp for consistency
            max_tokens=1200,  # Reduced from 2000
        )
        
        batch_result = _parse_json_response(response.choices[0].message.content)
        
        # Map back to page IDs
        result = {}
        for idx, page in enumerate(slide_pages):
            page_kps = []
            if isinstance(batch_result, dict):
                page_kps = batch_result.get(str(idx)) or batch_result.get(idx) or []
            result[page.id] = page_kps if isinstance(page_kps, list) else []
        
        return result
        
    except Exception as e:
        logger.error("OpenAI batch KP extraction error: %s", e)
        # Fallback to individual processing
        return {page.id: _fallback_extract_kp((page.content_text or "").strip()) 
                for page in slide_pages}


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

    def _normalize_kp_id(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

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

        # Attach video timestamps from linked KPs.
        # If the model omits or returns an invalid knowledge_point_id, fall back
        # to a known KP so every generated quiz can still jump to a key frame.
        kp_map = {kp["id"]: kp for kp in kp_list}
        for index, item in enumerate(results):
            kp_id = _normalize_kp_id(item.get("knowledge_point_id"))
            linked_kp = kp_map.get(kp_id)

            if linked_kp is None and kp_list:
                linked_kp = kp_list[index % len(kp_list)]
                item["knowledge_point_id"] = linked_kp["id"]
            elif linked_kp is not None:
                item["knowledge_point_id"] = linked_kp["id"]

            item["video_timestamp"] = linked_kp.get("video_timestamp") if linked_kp else None

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
