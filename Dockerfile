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
    libpq-dev gcc ffmpeg libreoffice-core libreoffice-impress && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend-build /frontend/build ./static_frontend

RUN mkdir -p uploads/slides uploads/videos

EXPOSE ${PORT:-5000}

ENV PORT=${PORT:-5000}
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 1800 --log-level info --access-logfile - --error-logfile - run:app
