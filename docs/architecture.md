# Architecture

## Overview
SyncLearn is a Flask + React application for course content ingestion, AI-assisted Q&A, knowledge-point extraction, quiz generation, and teacher analytics.

The backend follows feature-based blueprints and uses Supabase as the only database access layer for application data.

## Backend Architecture

### Application Entry
- [backend/run.py](backend/run.py): starts Flask app via [backend/app/__init__.py](backend/app/__init__.py).
- [backend/app/__init__.py](backend/app/__init__.py): configures CORS, initializes Supabase client from config, and registers API blueprints.

### API Layer (Flask Blueprints)
- [backend/app/api/courses.py](backend/app/api/courses.py): course CRUD.
- [backend/app/api/slides.py](backend/app/api/slides.py): slide upload/processing and slide retrieval.
- [backend/app/api/videos.py](backend/app/api/videos.py): chunked uploads, stream URLs, transcription orchestration.
- [backend/app/api/chat.py](backend/app/api/chat.py): chat history and message exchange.
- [backend/app/api/knowledge_points.py](backend/app/api/knowledge_points.py): async KP extraction and alignment endpoints.
- [backend/app/api/quizzes.py](backend/app/api/quizzes.py): quiz generation, attempts, statistics.
- [backend/app/api/dashboard.py](backend/app/api/dashboard.py): teacher-facing analytics and AI review brief.

### Service Layer
- [backend/app/services/supabase_repo.py](backend/app/services/supabase_repo.py): shared Supabase CRUD/query utilities and response serializers.
- [backend/app/services/ai_service.py](backend/app/services/ai_service.py): chat, KP extraction, and quiz generation using OpenAI-compatible APIs.
- [backend/app/services/alignment_service.py](backend/app/services/alignment_service.py): transcript generation, embeddings, and semantic alignment.
- [backend/app/services/s3_service.py](backend/app/services/s3_service.py): S3 storage abstraction.

### Data Stores
- Supabase Postgres stores all structured learning/application data.
- S3 stores binary assets: uploaded slides/videos and derived thumbnails.

## Data Flow (High Level)
1. Upload media to S3 and persist metadata to Supabase tables.
2. Process slide/video content in backend services and write extracted artifacts (pages, transcripts, embeddings, KPs) to Supabase.
3. AI endpoints gather context from Supabase tables and generate responses/quizzes.
4. Dashboard endpoints aggregate quiz/chat/KP metrics from Supabase for instructor insights.

## Frontend Architecture
- React SPA in [frontend/src](frontend/src) consumes backend REST endpoints.
- Feature components map directly to backend domains (chat, slides, videos, quizzes, dashboard).

## Deployment Notes
- Backend and frontend are designed for Vercel-compatible deployment.
- Supabase credentials and storage/LLM credentials are provided via environment variables.
