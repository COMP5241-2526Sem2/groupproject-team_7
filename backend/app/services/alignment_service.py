import logging
import math
import os
import struct
import threading

from flask import current_app
from openai import OpenAI

from app import db
from app.models.course import Course
from app.models.knowledge_point import KnowledgePoint
from app.models.slide import Slide, SlidePage
from app.models.video import Video
from app.models.video_transcript import VideoTranscript

logger = logging.getLogger(__name__)

# Global model cache for faster-whisper to avoid reloading on every transcription
_WHISPER_MODEL_CACHE = {}
_WHISPER_MODEL_LOCK = threading.Lock()

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client():
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    base_url = current_app.config.get("OPENAI_BASE_URL", "") or None
    return OpenAI(api_key=api_key, base_url=base_url)


def _embedding_model():
    return current_app.config.get("OPENAI_EMBEDDING_MODEL", EMBEDDING_MODEL)


def _serialize_embedding(vec):
    """Pack a list of floats into bytes (float32 little-endian)."""
    return struct.pack(f"<{len(vec)}f", *vec)


def _deserialize_embedding(data):
    """Unpack bytes back to a list of floats."""
    n = len(data) // 4
    return list(struct.unpack(f"<{n}f", data))


def _cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _progress(callback, stage, percent, message):
    if callback:
        try:
            callback(stage, percent, message)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Embeddings — batch embed text via OpenAI
# ---------------------------------------------------------------------------

def _get_embeddings(texts, client):
    """Get embeddings for a list of texts. Returns list of float lists."""
    if not texts:
        return []
    all_embeddings = []
    batch_size = 512
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.embeddings.create(model=_embedding_model(), input=batch)
        for item in resp.data:
            all_embeddings.append(item.embedding)
    return all_embeddings


def embed_slide_pages(slide_id, client=None):
    """Generate and store embeddings for all pages of a slide."""
    if client is None:
        client = _get_client()
    if client is None:
        return

    slide = db.session.get(Slide, slide_id)
    if not slide:
        return

    pages = sorted(slide.pages, key=lambda p: p.page_number)
    texts = [p.content_text for p in pages if (p.content_text or "").strip()]
    valid_pages = [p for p in pages if (p.content_text or "").strip()]

    if not texts:
        return

    try:
        embeddings = _get_embeddings(texts, client)
        for page, emb in zip(valid_pages, embeddings):
            page.embedding = _serialize_embedding(emb)
        db.session.commit()
    except Exception as exc:
        logger.error("Slide embedding failed: %s", exc)
        db.session.rollback()


# ---------------------------------------------------------------------------
# Video transcription — uploaded videos only
# ---------------------------------------------------------------------------

def _transcribe_model():
    return current_app.config.get("FASTER_WHISPER_MODEL", "tiny")


def _response_segments(response):
    segments = []
    raw_segments = None
    if isinstance(response, dict):
        raw_segments = response.get("segments")
    else:
        raw_segments = getattr(response, "segments", None)

    if raw_segments:
        for index, segment in enumerate(raw_segments):
            if isinstance(segment, dict):
                segments.append({
                    "segment_index": int(segment.get("id", index)),
                    "start_time": float(segment.get("start", 0) or 0),
                    "end_time": float(segment.get("end", 0) or 0),
                    "text": str(segment.get("text", "") or "").strip(),
                })
            else:
                segments.append({
                    "segment_index": index,
                    "start_time": float(getattr(segment, "start", 0) or 0),
                    "end_time": float(getattr(segment, "end", 0) or 0),
                    "text": str(getattr(segment, "text", "") or "").strip(),
                })
        return segments

    text = ""
    if isinstance(response, dict):
        text = str(response.get("text", "") or "").strip()
    else:
        text = str(getattr(response, "text", "") or "").strip()

    if text:
        segments.append({
            "segment_index": 0,
            "start_time": 0.0,
            "end_time": 0.0,
            "text": text,
        })
    return segments


def _transcribe_via_api(video_path, client, progress_cb=None):
    _progress(progress_cb, "transcribing", 10, "Uploading video for transcription...")
    with open(video_path, "rb") as handle:
        response = client.audio.transcriptions.create(
            model=current_app.config.get("OPENAI_TRANSCRIPTION_MODEL", "whisper-1"),
            file=handle,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    segments = _response_segments(response)
    _progress(progress_cb, "transcribing", 80, f"Received {len(segments)} transcript segments.")
    return segments


def _get_cached_whisper_model(model_name, device, compute_type, cache_dir):
    """Get or create cached WhisperModel instance for reuse across requests."""
    model_key = f"{model_name}:{device}:{compute_type}"
    
    # Check if model is already cached
    if model_key in _WHISPER_MODEL_CACHE:
        return _WHISPER_MODEL_CACHE[model_key]
    
    # Load model once and cache it
    with _WHISPER_MODEL_LOCK:
        # Double-check after acquiring lock
        if model_key in _WHISPER_MODEL_CACHE:
            return _WHISPER_MODEL_CACHE[model_key]
        
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            raise Exception(f"faster-whisper is not installed: {exc}")
        
        logger.info(f"Creating new cached Whisper model: {model_key}")
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["HF_HOME"] = cache_dir
        
        model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            download_root=cache_dir,
        )
        _WHISPER_MODEL_CACHE[model_key] = model
        logger.info(f"Model cached: {model_key}")
        return model


def _transcribe_via_local(video_path, progress_cb=None):
    _progress(progress_cb, "transcribing", 10, "Preparing transcription...")
    try:
        device = current_app.config.get("FASTER_WHISPER_DEVICE", "cpu")
        compute_type = current_app.config.get("FASTER_WHISPER_COMPUTE_TYPE", "int8")
        beam_size = current_app.config.get("FASTER_WHISPER_BEAM_SIZE", 1)  # Default to 1 for speed
        vad_filter = current_app.config.get("FASTER_WHISPER_VAD_FILTER", True)  # Default to True to skip silence
        cache_dir = current_app.config.get("FASTER_WHISPER_CACHE_DIR", "./whisper_models")
        model_name = _transcribe_model()
        
        _progress(progress_cb, "transcribing", 15, f"Loading {model_name} model...")
        logger.info(f"Transcribing with model={model_name}, device={device}, compute_type={compute_type}, beam_size={beam_size}, vad_filter={vad_filter}")
        
        # Get cached model (loads only once)
        model = _get_cached_whisper_model(model_name, device, compute_type, cache_dir)
        
        _progress(progress_cb, "transcribing", 25, "Transcribing audio...")
        segments_iter, _info = model.transcribe(video_path, beam_size=beam_size, vad_filter=vad_filter)
        segments = []
        for index, segment in enumerate(segments_iter):
            text = (segment.text or "").strip()
            if not text:
                continue
            segments.append({
                "segment_index": index,
                "start_time": float(segment.start or 0),
                "end_time": float(segment.end or 0),
                "text": text,
            })
        _progress(progress_cb, "transcribing", 80, f"Transcribed {len(segments)} segments.")
        return segments
    except Exception as exc:
        logger.error(f"Local transcription failed: {exc}", exc_info=True)
        return {"error": f"Local transcription failed: {exc}"}


def transcribe_video(video_id, progress_cb=None):
    """Transcribe an uploaded video into transcript segments using local faster-whisper."""
    video = db.session.get(Video, video_id)
    if not video:
        return {"error": "Video not found"}
    if video.is_external():
        return {"error": "External video links cannot be transcribed. Upload a local video file instead."}
    if not video.file_path or not os.path.exists(video.file_path):
        return {"error": "Uploaded video file is missing"}

    _progress(progress_cb, "starting", 0, "Preparing transcription...")
    VideoTranscript.query.filter_by(video_id=video_id).delete()
    db.session.commit()

    # Skip OpenAI API and use local transcription directly
    use_local_only = current_app.config.get("TRANSCRIBE_USE_LOCAL_ONLY", True)
    if isinstance(use_local_only, str):
        use_local_only = use_local_only.lower() == "true"
    transcript_segments = None
    
    if not use_local_only:
        client = _get_client()
        if client is not None:
            try:
                transcript_segments = _transcribe_via_api(video.file_path, client, progress_cb)
            except Exception as exc:
                logger.warning("OpenAI transcription failed for video %s: %s", video_id, exc)

    # Use local transcription if API not used or API failed
    if not transcript_segments:
        logger.info("Using local faster-whisper for transcription...")
        transcript_segments = _transcribe_via_local(video.file_path, progress_cb)

    if isinstance(transcript_segments, dict) and transcript_segments.get("error"):
        return transcript_segments

    created = []
    for segment in transcript_segments:
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        transcript = VideoTranscript(
            video_id=video.id,
            segment_index=int(segment.get("segment_index", len(created))),
            start_time=float(segment.get("start_time", 0) or 0),
            end_time=float(segment.get("end_time", 0) or 0),
            text=text,
        )
        db.session.add(transcript)
        created.append(transcript)

    video.processed = True
    db.session.commit()
    _progress(progress_cb, "done", 100, f"Completed! {len(created)} transcript segments generated.")
    return [item.to_dict() for item in created]


def get_video_transcript(video_id):
    return [
        transcript.to_dict()
        for transcript in (
            VideoTranscript.query.filter_by(video_id=video_id)
            .order_by(VideoTranscript.segment_index.asc())
            .all()
        )
    ]


# ---------------------------------------------------------------------------
# Knowledge point alignment — duration-based fallback
# ---------------------------------------------------------------------------

def _select_course_video(course_id):
    videos = (
        Video.query.filter_by(course_id=course_id)
        .order_by(Video.created_at.asc())
        .all()
    )
    if not videos:
        return None

    for video in videos:
        if video.duration and video.duration > 0:
            return video

    return videos[0]


def align_all_knowledge_points(course_id):
    """Re-align all knowledge points for a course using slide-page timing."""
    course = db.session.get(Course, course_id)
    if not course:
        return {"error": "Course not found"}

    video = _select_course_video(course_id)
    if not video:
        return {"error": "No video found for this course"}
    if not video.duration or video.duration <= 0:
        return {"error": "Video has no duration metadata"}

    slides = Slide.query.filter_by(course_id=course_id).all()
    page_ids = []
    pages_by_id = {}
    for slide in slides:
        for page in slide.pages:
            page_ids.append(page.id)
            pages_by_id[page.id] = page

    if not page_ids:
        return {"error": "No slide pages found"}

    kps = KnowledgePoint.query.filter(
        KnowledgePoint.slide_page_id.in_(page_ids)
    ).all()
    if not kps:
        return {"error": "No knowledge points found"}

    total_pages = max(sum(1 for _ in pages_by_id.values()), 1)
    updated = 0
    for kp in kps:
        page = pages_by_id.get(kp.slide_page_id)
        if not page:
            continue
        fraction = (page.page_number - 1) / total_pages
        kp.video_id = video.id
        kp.video_timestamp = round(fraction * video.duration, 1)
        kp.confidence = 0.3
        updated += 1

    db.session.commit()
    return {"updated": updated, "total": len(kps)}
