import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


class Config:
    """Base configuration for the application.
    
    This class handles configuration for:
    - Flask application settings (SECRET_KEY, etc.)
    - Supabase client initialization for Postgres REST operations
    - Redis configuration for async task processing
    - AWS S3 configuration for file storage
    - OpenAI API configuration for AI services
    """
    
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    
    # Supabase Client Configuration
    # Initialize Supabase client if SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are provided
    _supabase_url = os.environ.get("SUPABASE_URL", "")
    _supabase_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    SUPABASE_CLIENT = None
    if _supabase_url and _supabase_key:
        try:
            # Initialize Supabase client for REST API operations
            # This allows for direct interaction with Supabase services via the official client SDK
            SUPABASE_CLIENT = create_client(_supabase_url, _supabase_key)
        except Exception as e:
            print(f"Error initializing Supabase client. Check SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY.")
    
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))  # 50MB per request (chunks are 5MB)
    
    # Redis configuration for Vercel Redis or local Redis
    # Used as broker for Celery async task queue
    _redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = _redis_url
    CELERY_RESULT_BACKEND = _redis_url
    
    # AWS S3 Configuration for file storage (slides, videos, thumbnails)
    # Enables storing large media files in object storage rather than database
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_S3_REGION = os.environ.get("AWS_S3_REGION", "")
    AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET", "")
    # Optional: Custom S3 endpoint for S3-compatible services (e.g., MinIO)
    AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", None)
    # Temporary file directory for processing uploads
    TEMP_UPLOAD_DIR = os.environ.get("TEMP_UPLOAD_DIR", "/tmp/synclearn_uploads")
    
    # LLM Configuration
    # Prefer GitHub Models when GITHUB_TOKEN is available, while preserving OpenAI compatibility.
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
    GITHUB_MODELS_ENDPOINT = os.environ.get("GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "") or GITHUB_TOKEN
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "") or (GITHUB_MODELS_ENDPOINT if GITHUB_TOKEN else "")
    OPENAI_CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "openai/gpt-4.1")
    OPENAI_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "openai/text-embedding-3-small")


class DevelopmentConfig(Config):
    """Development configuration with debug mode enabled."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration with debug mode disabled."""
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
