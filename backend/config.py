import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


class Config:
    """Base configuration for the application.
    
    This class handles configuration for:
    - Flask application settings (SECRET_KEY, etc.)
    - Database connection (PostgreSQL via Supabase or direct connection)
    - Supabase client initialization for REST API operations
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
            print(f"Error initializing Supabase client: {e}")
            #pass  # Supabase client is optional; DB operations can still work with DATABASE_URL
    
    # Database Configuration
    # Priority: SUPABASE_URL (via constructed connection string) > DATABASE_URL > SQLite fallback
    _db_url = os.environ.get("DATABASE_URL", "")
    

    # Fall back to SQLite for local/test environments
    if not _db_url:
        _db_url = "sqlite:///synclearn.db"
    
    print(f"Using database URL: {_db_url}")
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
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
    
    # OpenAI Configuration
    # Provides access to GPT models for AI-powered features and embeddings
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")  # e.g. https://models.inference.ai.azure.com
    OPENAI_CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "")
    OPENAI_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "")


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
