# Build frontend assets
FROM m.daocloud.io/docker.io/library/node:20-bookworm-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# Backend runtime image (includes built frontend)
FROM m.daocloud.io/docker.io/library/python:3.11-slim-bookworm

WORKDIR /app

# Install minimal system dependencies
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g; s|http://deb.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g; s|http://deb.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list; \
    fi; \
    printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\n' > /etc/apt/apt.conf.d/80-retries
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libpq-dev \
      curl && \
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

# Copy and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  --trusted-host pypi.tuna.tsinghua.edu.cn \
  --retries 10 \
  --timeout 120 \
  -r requirements.txt

# Copy backend application code
COPY backend/ .

# Copy built React app for Flask to serve as static frontend
COPY --from=frontend-builder /frontend/build/ /app/static_frontend/

RUN mkdir -p uploads/slides/thumbnails uploads/videos whisper_models

EXPOSE 5000

ENV PORT=5000
ENV FASTER_WHISPER_CACHE_DIR=/app/whisper_models
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 1 --timeout 1800 --log-level info --access-logfile - --error-logfile - run:app"]
