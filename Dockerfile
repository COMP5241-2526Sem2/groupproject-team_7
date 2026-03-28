# Stage 1: Build frontend
FROM node:18-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install --legacy-peer-deps
COPY frontend/ .
RUN npm run build

# Stage 2: Backend + serve frontend static files
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    libmupdf-dev libfreetype6-dev libharfbuzz-dev libjpeg-dev libopenjp2-7-dev \
    libreoffice-impress --no-install-recommends \
    ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the faster-whisper model so it's cached in the image
# (avoids lengthy download at runtime on Railway)
# Use "tiny" by default for fast transcription on limited-CPU cloud platforms
ARG WHISPER_MODEL=tiny
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')"

COPY backend/ .
COPY --from=frontend-build /frontend/build ./static_frontend

RUN mkdir -p uploads/slides/thumbnails uploads/videos

EXPOSE ${PORT:-5000}

ENV PORT=${PORT:-5000}
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 1800 --log-level info --access-logfile - --error-logfile - run:app
