import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    _db_url = os.environ.get(
        "DATABASE_URL", "sqlite:///synclearn.db"
    )
    # Handle multiple database URL formats:
    # - Supabase: postgresql://user:password@host:port/database?sslmode=require
    # - Railway: postgres://user:password@host:port/database
    # - Local: postgresql://user:password@localhost:5432/database
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))  # 50MB per request (chunks are 5MB)
    
    # Redis configuration for Vercel Redis or local Redis
    _redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = _redis_url
    CELERY_RESULT_BACKEND = _redis_url
    
    # AWS S3 Configuration for file storage (slides, videos, thumbnails)
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_S3_REGION = os.environ.get("AWS_S3_REGION", "us-east-1")
    AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET", "")
    # Optional: Custom S3 endpoint for S3-compatible services (e.g., MinIO)
    AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", None)
    # Temporary file directory for processing uploads
    TEMP_UPLOAD_DIR = os.environ.get("TEMP_UPLOAD_DIR", "/tmp/synclearn_uploads")
    
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")  # e.g. https://models.inference.ai.azure.com
    OPENAI_CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    OPENAI_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
