import os
from dotenv import load_dotenv

# Load .env file if it exists (for local development)
load_dotenv()

# Lazy import supabase to handle missing credentials gracefully
def _get_supabase_client():
    """Lazily create Supabase client to avoid import errors when credentials are missing."""
    try:
        from supabase import create_client
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
        if supabase_url and supabase_key:
            return create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
    return None


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
    # Use lazy initialization to avoid import errors during Vercel build
    SUPABASE_CLIENT = _get_supabase_client()
    
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))  # 50MB per request (chunks are 5MB)
    
    # Upstash Redis configuration (serverless-compatible)
    # Used for caching, rate limiting, and async task queue
    UPSTASH_REDIS_REST_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
    UPSTASH_REDIS_REST_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
    
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
