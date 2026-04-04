# Backend only (Frontend is in separate Docker service)
FROM m.daocloud.io/docker.io/library/python:3.11-slim

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install only essential FFmpeg (without encoding libraries)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install only LibreOffice Impress (minimal install)
# Skip language packs, gallery, templates to reduce size
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      --no-install-suggests \
      libreoffice-impress \
      fonts-noto && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /usr/share/libreoffice/help/* && \
    rm -rf /usr/share/libreoffice/extensions/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the faster-whisper models so they're cached in the image
# (avoids lengthy download at runtime on Railway)
RUN python - <<'PY'
from faster_whisper import WhisperModel

for model_size in ['tiny', 'base']:
  try:
    print(f'Preloading {model_size} model...')
    WhisperModel(model_size, device='cpu', compute_type='int8')
    print(f'✓ Preloaded {model_size} model successfully')
  except Exception as exc:
    # Do not fail image build when external model registry is temporarily unavailable.
    print(f'WARNING: skipping {model_size} model pre-download due to: {exc}')
PY

COPY backend/ .

RUN mkdir -p uploads/slides/thumbnails uploads/videos

EXPOSE 5000

ENV PORT=${PORT:-5000}
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 1800 --log-level info --access-logfile - --error-logfile - run:app
