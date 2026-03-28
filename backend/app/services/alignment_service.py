"""
Alignment service: ASR transcription, embedding generation, and semantic matching.

Provides the Phase 2 semantic alignment engine:
  1. ASR — Transcribe video audio via OpenAI Whisper
  2. Embeddings — Generate text embeddings via OpenAI text-embedding-3-small
  3. Alignment — Match slide knowledge points to video transcript segments
"""

import logging
import math
import os
import struct
import subprocess
import tempfile

from flask import current_app
from openai import OpenAI

from app import db
from app.models.video import Video
from app.models.video_transcript import VideoTranscript
from app.models.slide import Slide, SlidePage
from app.models.knowledge_point import KnowledgePoint

logger = logging.getLogger(__name__)

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
    return current_app.config.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


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


# ---------------------------------------------------------------------------
# 1. ASR — Transcribe video via OpenAI Whisper
# ---------------------------------------------------------------------------

def _extract_audio(video_path):
    """Extract audio from a video file to a temporary WAV file using ffmpeg."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vn",                # no video
                "-acodec", "pcm_s16le",
                "-ar", "16000",       # 16 kHz mono — ideal for Whisper
                "-ac", "1",
                tmp.name,
            ],
            check=True,
            capture_output=True,
        )
        return tmp.name
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.error("ffmpeg audio extraction failed: %s", exc)
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        return None


def _split_audio_chunks(audio_path, max_size_mb=24):
    """Split an audio file into chunks smaller than max_size_mb.

    Returns a list of (chunk_path, offset_seconds) tuples.
    """
    file_size = os.path.getsize(audio_path)
    max_bytes = max_size_mb * 1024 * 1024

    if file_size <= max_bytes:
        return [(audio_path, 0.0)]

    # Get total duration
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True,
    )
    total_duration = float(result.stdout.strip())

    # Calculate chunk duration to stay under size limit
    num_chunks = math.ceil(file_size / max_bytes)
    chunk_duration = total_duration / num_chunks

    chunks = []
    for i in range(num_chunks):
        start = i * chunk_duration
        chunk_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", audio_path,
                "-ss", str(start),
                "-t", str(chunk_duration),
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                chunk_path,
            ],
            check=True,
            capture_output=True,
        )
        chunks.append((chunk_path, start))

    return chunks


def _transcribe_via_api(audio_path, client, progress_cb=None):
    """Transcribe audio using OpenAI Whisper API (fast, works on any server)."""

    def _progress(stage, percent, message):
        if progress_cb:
            try:
                progress_cb(stage, percent, message)
            except Exception:
                pass

    _progress("transcribing", 30, "Sending audio to Whisper API...")
    logger.info("Using OpenAI Whisper API for transcription")

    # Split audio into chunks if > 24MB (OpenAI limit is 25MB)
    chunks = _split_audio_chunks(audio_path, max_size_mb=24)
    all_segments = []

    for chunk_idx, (chunk_path, offset) in enumerate(chunks):
        pct = 30 + int((chunk_idx / max(len(chunks), 1)) * 45)
        _progress("transcribing", pct, f"Transcribing chunk {chunk_idx+1}/{len(chunks)}...")

        with open(chunk_path, "rb") as audio_file:
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

        for seg in (resp.segments or []):
            all_segments.append({
                "start": round(seg["start"] + offset, 2),
                "end": round(seg["end"] + offset, 2),
                "text": seg["text"].strip(),
            })

        # Clean up chunk file (but not the original)
        if chunk_path != audio_path and os.path.exists(chunk_path):
            os.unlink(chunk_path)

    return all_segments


def _transcribe_via_local(audio_path, progress_cb=None):
    """Transcribe audio using local faster-whisper model in a subprocess.

    Running in a subprocess isolates memory usage — if it OOMs, we get a
    clear error instead of silently killing the main process.
    """

    def _progress(stage, percent, message):
        if progress_cb:
            try:
                progress_cb(stage, percent, message)
            except Exception:
                pass

    import json as _json

    whisper_model = os.environ.get("WHISPER_MODEL", "tiny")
    _progress("transcribing", 25, f"Starting local transcription (model: {whisper_model})...")

    # Run transcription in a subprocess to isolate memory
    script = f'''
import json, sys
from faster_whisper import WhisperModel

model = WhisperModel("{whisper_model}", device="cpu", compute_type="int8", cpu_threads=1)
segments, info = model.transcribe(sys.argv[1], beam_size=1, vad_filter=True,
                                   vad_parameters=dict(min_silence_duration_ms=500))
result = []
for seg in segments:
    text = seg.text.strip()
    if not text:
        continue
    result.append({{"start": round(seg.start, 2), "end": round(seg.end, 2), "text": text}})
    # Print progress to stderr so parent can read it
    print(f"PROGRESS:{{len(result)}}", file=sys.stderr, flush=True)

print(json.dumps(result))
'''

    _progress("transcribing", 30, "Transcribing audio (subprocess)...")

    proc = subprocess.Popen(
        ["python", "-c", script, audio_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Read stderr for progress updates while process runs
    import selectors
    sel = selectors.DefaultSelector()
    sel.register(proc.stderr, selectors.EVENT_READ)

    stderr_lines = []
    while proc.poll() is None:
        events = sel.select(timeout=5)
        for key, _ in events:
            line = key.fileobj.readline()
            if line:
                line = line.strip()
                stderr_lines.append(line)
                if line.startswith("PROGRESS:"):
                    count = int(line.split(":")[1])
                    _progress("transcribing", min(30 + count, 78),
                              f"Transcribing... ({count} segments)")
        # Even if no events, update to show we're alive
        if not events:
            _progress("transcribing", 30, "Transcribing audio (working)...")

    sel.unregister(proc.stderr)
    sel.close()

    # Read remaining stderr
    remaining_err = proc.stderr.read()
    if remaining_err:
        stderr_lines.extend(remaining_err.strip().split('\n'))

    stdout = proc.stdout.read()
    proc.stdout.close()
    proc.stderr.close()

    if proc.returncode != 0:
        err_msg = '\n'.join(l for l in stderr_lines if not l.startswith("PROGRESS:"))
        logger.error("Local ASR subprocess failed (exit %d): %s", proc.returncode, err_msg[-500:])
        if proc.returncode == -9:
            raise RuntimeError("Transcription was killed (out of memory). Try a shorter video.")
        raise RuntimeError(f"Local transcription failed (exit {proc.returncode}): {err_msg[-300:]}")

    try:
        all_segments = _json.loads(stdout)
    except _json.JSONDecodeError:
        raise RuntimeError(f"Failed to parse transcription output. stderr: {' '.join(stderr_lines[-3:])}")

    return all_segments


def transcribe_video(video_id, progress_cb=None):
    """Run ASR on a video and store timestamped transcript segments.

    Strategy: try OpenAI Whisper API first (fast); fall back to local model.
    progress_cb: optional callback(stage, percent, message) for progress reporting.
    Returns list of created VideoTranscript dicts, or error dict.
    """

    def _progress(stage, percent, message):
        if progress_cb:
            try:
                progress_cb(stage, percent, message)
            except Exception:
                pass

    logger.info("Starting ASR for video %s", video_id)

    video = db.session.get(Video, video_id)
    if not video:
        return {"error": "Video not found"}

    if not os.path.exists(video.file_path):
        logger.error("Video file not found at %s", video.file_path)
        return {"error": "Video file not found on disk. Please re-upload the video."}

    # Remove old transcripts
    VideoTranscript.query.filter_by(video_id=video_id).delete()
    db.session.flush()

    _progress("extract_audio", 5, "Extracting audio from video...")
    audio_path = _extract_audio(video.file_path)
    if audio_path is None:
        return {"error": "Failed to extract audio from video (is ffmpeg installed?)"}

    try:
        raw_segments = None

        # --- Try OpenAI Whisper API first (fast, reliable) ---
        client = _get_client()
        if client:
            try:
                _progress("transcribing", 20, "Trying Whisper API...")
                raw_segments = _transcribe_via_api(audio_path, client, progress_cb)
                logger.info("Whisper API transcription succeeded: %d segments", len(raw_segments))
            except Exception as api_err:
                logger.warning("Whisper API failed (%s), falling back to local model", api_err)
                _progress("transcribing", 20, "API unavailable, switching to local model...")
                raw_segments = None

        # --- Fallback to local faster-whisper ---
        if raw_segments is None:
            raw_segments = _transcribe_via_local(audio_path, progress_cb)
            logger.info("Local transcription completed: %d segments", len(raw_segments))

        _progress("saving", 80, "Saving transcript to database...")

        segments_created = []
        for idx, seg_data in enumerate(raw_segments):
            ts = VideoTranscript(
                video_id=video_id,
                segment_index=idx,
                start_time=seg_data["start"],
                end_time=seg_data["end"],
                text=seg_data["text"],
            )
            db.session.add(ts)
            segments_created.append(ts)

        # Update video duration from the last segment if we got any
        if segments_created:
            video.duration = segments_created[-1].end_time

        video.processed = True
        db.session.commit()

        # Generate embeddings for transcript segments
        if client:
            _progress("embedding", 88, "Generating embeddings for semantic alignment...")
            _embed_transcripts(video_id, client)

        _progress("done", 100, f"Completed! {len(segments_created)} segments transcribed.")
        return [t.to_dict() for t in segments_created]

    except Exception as exc:
        db.session.rollback()
        logger.error("ASR transcription failed: %s", exc)
        return {"error": f"Transcription failed: {type(exc).__name__}: {exc}"}
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)


# ---------------------------------------------------------------------------
# 2. Embeddings — batch embed text via OpenAI
# ---------------------------------------------------------------------------

def _get_embeddings(texts, client):
    """Get embeddings for a list of texts. Returns list of float lists."""
    if not texts:
        return []
    # OpenAI allows up to 2048 inputs per call; batch if needed
    all_embeddings = []
    batch_size = 512
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.embeddings.create(model=_embedding_model(), input=batch)
        for item in resp.data:
            all_embeddings.append(item.embedding)
    return all_embeddings


def _embed_transcripts(video_id, client=None):
    """Generate and store embeddings for all transcript segments of a video."""
    if client is None:
        client = _get_client()
    if client is None:
        return

    segments = (
        VideoTranscript.query
        .filter_by(video_id=video_id)
        .order_by(VideoTranscript.segment_index)
        .all()
    )
    texts = [s.text for s in segments if s.text.strip()]
    valid_segments = [s for s in segments if s.text.strip()]

    if not texts:
        return

    try:
        embeddings = _get_embeddings(texts, client)
        for seg, emb in zip(valid_segments, embeddings):
            seg.embedding = _serialize_embedding(emb)
        db.session.commit()
    except Exception as exc:
        logger.error("Embedding generation failed: %s", exc)
        db.session.rollback()


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
# 3. Semantic Alignment — match KP text to transcript segments
# ---------------------------------------------------------------------------

def align_knowledge_point(kp_text, video_id, client=None):
    """Find the best-matching transcript segment for a knowledge point.

    Returns (timestamp, confidence) or (None, 0.0) if no match found.
    """
    if client is None:
        client = _get_client()
    if client is None:
        return None, 0.0

    segments = (
        VideoTranscript.query
        .filter_by(video_id=video_id)
        .filter(VideoTranscript.embedding.isnot(None))
        .order_by(VideoTranscript.segment_index)
        .all()
    )
    if not segments:
        return None, 0.0

    try:
        kp_embedding = _get_embeddings([kp_text], client)[0]
    except Exception as exc:
        logger.error("KP embedding failed: %s", exc)
        return None, 0.0

    best_sim = -1.0
    best_seg = None
    for seg in segments:
        seg_emb = _deserialize_embedding(seg.embedding)
        sim = _cosine_similarity(kp_embedding, seg_emb)
        if sim > best_sim:
            best_sim = sim
            best_seg = seg

    if best_seg is None:
        return None, 0.0

    # Use the segment's start_time as the timestamp
    return best_seg.start_time, round(best_sim, 4)


def align_all_knowledge_points(course_id):
    """Re-align all knowledge points for a course using semantic matching.

    This replaces the naive linear interpolation with actual embedding similarity.
    Returns the number of knowledge points updated.
    """
    client = _get_client()
    if client is None:
        return {"error": "OpenAI API key not configured"}

    # Get the primary video for this course (first one)
    video = (
        Video.query
        .filter_by(course_id=course_id)
        .order_by(Video.created_at.asc())
        .first()
    )
    if not video:
        return {"error": "No video found for this course"}

    # Check if video has transcripts with embeddings
    transcript_count = (
        VideoTranscript.query
        .filter_by(video_id=video.id)
        .filter(VideoTranscript.embedding.isnot(None))
        .count()
    )
    if transcript_count == 0:
        return {"error": "Video has no transcripts. Process the video first."}

    # Get all knowledge points for this course
    slides = Slide.query.filter_by(course_id=course_id).all()
    page_ids = []
    for s in slides:
        page_ids.extend([p.id for p in s.pages])

    if not page_ids:
        return {"error": "No slide pages found"}

    kps = KnowledgePoint.query.filter(
        KnowledgePoint.slide_page_id.in_(page_ids)
    ).all()

    if not kps:
        return {"error": "No knowledge points found"}

    # Build KP text for batch embedding
    kp_texts = [f"{kp.title}. {kp.content}" for kp in kps]
    kp_embeddings = _get_embeddings(kp_texts, client)

    # Load all transcript embeddings
    segments = (
        VideoTranscript.query
        .filter_by(video_id=video.id)
        .filter(VideoTranscript.embedding.isnot(None))
        .order_by(VideoTranscript.segment_index)
        .all()
    )
    seg_embeddings = [_deserialize_embedding(s.embedding) for s in segments]

    updated = 0
    for kp, kp_emb in zip(kps, kp_embeddings):
        best_sim = -1.0
        best_seg = None
        for seg, seg_emb in zip(segments, seg_embeddings):
            sim = _cosine_similarity(kp_emb, seg_emb)
            if sim > best_sim:
                best_sim = sim
                best_seg = seg

        if best_seg is not None:
            kp.video_id = video.id
            kp.video_timestamp = best_seg.start_time
            kp.confidence = round(best_sim, 4)
            updated += 1

    db.session.commit()
    return {"updated": updated, "total": len(kps)}


def get_video_transcript(video_id):
    """Get full transcript text for a video, sorted by time."""
    segments = (
        VideoTranscript.query
        .filter_by(video_id=video_id)
        .order_by(VideoTranscript.start_time)
        .all()
    )
    return [s.to_dict() for s in segments]
