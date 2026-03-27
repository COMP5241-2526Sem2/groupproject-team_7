# Technology Stack

This document outlines the technologies, frameworks, libraries, and tools used in the SyncLearn project.

## Backend Technologies

### Framework & Server
- Flask 3.1.0 - Python web framework used for REST APIs.
- Gunicorn 23.0.0 - Production WSGI server.
- Werkzeug 3.1.3 - Request/response and WSGI utilities used by Flask.

### Database & Data Access
- Supabase (PostgreSQL) - Primary managed database for production and local-compatible environments.
- Supabase Python Client 2.0+ - Official client used by backend APIs/services for CRUD via PostgREST.
- psycopg2-binary 2.9.10 - PostgreSQL driver used by migration/utility scripts.

### API & Middleware
- Flask-CORS 5.0.1 - Cross-origin API access for frontend integration.

### AI & NLP Services
- openai Python client 1.68.0 - OpenAI-compatible SDK used for chat, extraction, quizzes, and embeddings.
- GitHub Models (preferred) - Default LLM endpoint via OpenAI-compatible interface.
  - openai/gpt-4.1 - Default chat/completion model.
  - openai/text-embedding-3-small - Default embedding model.
- OpenAI-compatible providers (optional) - Supported via OPENAI_API_KEY and OPENAI_BASE_URL overrides.

### File Processing & Content Handling
- PyPDF2 3.0.1 - PDF parsing utilities.
- PyMuPDF 1.25.3 - PDF rendering and thumbnail generation.
- python-pptx 1.0.2 - PowerPoint text extraction.
- numpy >= 2.0.2 - Numerical operations and vector utilities.

### Storage & Async Infrastructure
- boto3 >= 1.34.0 - AWS S3/S3-compatible object storage integration.
- AWS S3 - Storage for slide/video files and generated thumbnails.
- Celery >= 5.3.0 - Async task queue support.
- Redis / Vercel Redis - Broker/result backend for Celery.

### Utilities
- python-dotenv 1.1.0 - Environment variable loading.
- requests >= 2.31.0 - HTTP client utilities.

## Frontend Technologies

### Framework & Libraries
- React 18.3.1 - Component-driven UI.
- React DOM 18.3.1 - DOM renderer.
- react-scripts 5.0.1 - CRA build tooling.

### HTTP & API Communication
- Axios 1.7.9 - Frontend-to-backend API requests.

### Styling
- CSS modules by feature in frontend/src/styles.

## Deployment & DevOps

### Platforms
- Vercel - Web app and API deployment target.
- Supabase - PostgreSQL hosting.
- AWS S3 - Media object storage.
- Redis (including Vercel Redis) - Async infrastructure.

### Environment Configuration
- Core database vars: SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY.
- Preferred LLM vars: GITHUB_TOKEN and optional GITHUB_MODELS_ENDPOINT.
- Provider overrides: OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_CHAT_MODEL, OPENAI_EMBEDDING_MODEL.
- Storage vars: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_REGION, AWS_S3_BUCKET.
- Redis var: REDIS_URL.

## Architecture Highlights
- Backend uses Supabase client queries in API/service layers instead of SQLAlchemy ORM.
- Flask blueprints expose feature-scoped REST endpoints under /api/*.
- AI services consume course materials from Supabase-backed tables for RAG-like responses and quiz/KP generation.
- Media files are stored in S3 while metadata and learning data remain in Supabase Postgres.
