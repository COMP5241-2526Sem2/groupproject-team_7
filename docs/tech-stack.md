# Technology Stack

This document outlines the technologies, frameworks, libraries, and tools used in the SyncLearn project.

## Backend Technologies

### Framework & Server
- **Flask 3.1.0** - Lightweight Python web framework used as the primary application framework for building RESTful APIs
- **Gunicorn 23.0.0** - WSGI HTTP Server used for running the Flask application in production environments
- **Werkzeug 3.1.3** - WSGI utility library that provides the foundation for Flask's request/response handling

### Database & ORM
- **PostgreSQL 16** (via Docker) - Primary relational database used for production data storage
- **SQLite** - Fallback database for local development when PostgreSQL is unavailable
- **SQLAlchemy 3.1.1** (via Flask-SQLAlchemy) - ORM for database abstraction and query management
- **Flask-Migrate 4.1.0** - Database migration tool that manages schema changes and versions
- **psycopg2-binary 2.9.10** - PostgreSQL adapter for Python

### API & Middleware
- **Flask-CORS 5.0.1** - Middleware that enables Cross-Origin Resource Sharing for API endpoints

### AI & NLP Services
- **OpenAI Python Client 1.68.0** - Official SDK for integrating OpenAI APIs
  - **GPT-4o-mini** - Language model used for chat assistance and content generation
  - **text-embedding-3-small** - Embedding model for semantic search and RAG (Retrieval Augmented Generation)
- **GitHub Models** - Alternative AI provider support via OpenAI-compatible API endpoint

### File Processing & Content Handling
- **PyPDF2 3.0.1** - PDF parsing and manipulation library for extracting text from slide PDFs
- **PyMuPDF 1.25.3** - Advanced PDF library (alternative to PyPDF2) for PDF processing and thumbnail generation
- **python-pptx 1.0.2** - PowerPoint document creation and manipulation library for slide processing
- **numpy >= 2.0.2** - Numerical computing library used for mathematical operations and data processing

### Utilities
- **python-dotenv 1.1.0** - Environment variable management from .env files for configuration
- **requests >= 2.31.0** - HTTP library for making external API calls

### Task Queue & Caching (Infrastructure)
- **Celery** - Distributed task queue (configured but implementation details in config.py)
- **Redis** - In-memory data store used as Celery broker and result backend for async task management

## Frontend Technologies

### Framework & Libraries
- **React 18.3.1** - Modern JavaScript library for building interactive user interfaces with component-based architecture
- **React DOM 18.3.1** - React rendering library for DOM manipulation
- **react-scripts 5.0.1** - Build scripts and configuration from Create React App

### HTTP & API Communication
- **Axios 1.7.9** - Promise-based HTTP client for making API requests to the backend

### Styling
- **CSS** - Cascading Style Sheets with modular approach
  - Global styles in `global.css`
  - Component-specific stylesheets for ChatAssistant, CourseSelector, Header, QuizPanel, SlidesPanel, TeacherDashboard, and VideoPlayer

### Build & Development Tools
- **Create React App** - Zero-configuration build setup with webpack, babel, and eslint pre-configured

## Testing Tools

### Frontend Testing
- **Jest** (via react-scripts) - JavaScript testing framework included in Create React App for unit and integration testing

## Deployment & DevOps

### Containerization
- **Docker** - Container platform for packaging the application with all dependencies
  - Backend Dockerfile for Flask application
  - Frontend Dockerfile with nginx for serving static assets
- **Docker Compose** - Multi-container orchestration for local development (PostgreSQL + Flask app)

### Cloud Deployment
- **Render** - Cloud platform for hosting the application (render.yaml configuration file)
- **Nginx** - Reverse proxy and static file server used in the frontend Docker container

### Environment Configuration
- Development environment variables managed through `.env` files
- Production configuration through Render environment variables for API keys and model selection

## Architecture Highlights

### RESTful API Structure
The backend exposes multiple API endpoints organized by feature:
- `/api/courses` - Course management
- `/api/slides` - Slide content and thumbnails
- `/api/videos` - Video content and transcripts
- `/api/chat` - Chat assistance with AI
- `/api/knowledge-points` - Learning objectives and content alignment
- `/api/quizzes` - Quiz and assessment management
- `/api/dashboard` - Teacher analytics and dashboard data

### Frontend-Backend Communication
- Frontend uses Axios to communicate with backend APIs
- CORS enabled for cross-origin requests
- Proxy configuration in development for simplified API calls

### AI Integration
- OpenAI Chat API for conversational AI and content generation
- Text embeddings for semantic search and knowledge base retrieval
- Support for alternative providers via configurable base URL (e.g., GitHub Models via Azure)

### File Handling
- Support for PDF slides with text extraction and thumbnail generation
- PowerPoint file processing for slide content
- Organized upload folder structure for media files (slides, videos, thumbnails)
