import os
import sys

from flask import Flask, send_from_directory
from flask_cors import CORS

# Ensure backend directory is in path for imports
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

supabase_client = None  # Will be initialized in create_app if Supabase credentials are available


def create_app(config_name="default"):
    """Create and configure the Flask application.
    
    This function initializes:
    - Flask app instance
    - Supabase client for database REST API operations
    - CORS configuration
    - API blueprints
    - Frontend serving
    
    Args:
        config_name: Configuration class name ("default", "development", "production")
        
    Returns:
        Flask application instance with all components initialized
    """
    from config import config as config_map
    global supabase_client

    # Backend directory for reference
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Frontend build directory - check multiple possible locations for Vercel compatibility
    frontend_dir = os.path.join(backend_dir, "static_frontend")
    if not os.path.isdir(frontend_dir):
        # Fallback: check if frontend/build exists (local development)
        alt_frontend_dir = os.path.join(os.path.dirname(backend_dir), "frontend", "build")
        if os.path.isdir(alt_frontend_dir):
            frontend_dir = alt_frontend_dir
    app = Flask(__name__, static_folder=os.path.join(frontend_dir, "static"), static_url_path="/static")
    app.config.from_object(config_map[config_name])

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Initialize Supabase client from config so all data access goes through Supabase.
    if hasattr(config_map[config_name], 'SUPABASE_CLIENT') and config_map[config_name].SUPABASE_CLIENT:
        supabase_client = config_map[config_name].SUPABASE_CLIENT
        app.logger.info("Supabase client initialized successfully")
    else:
        app.logger.warning("Supabase client not initialized - check SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY")

    # os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    # os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "slides"), exist_ok=True)
    # os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "slides", "thumbnails"), exist_ok=True)
    # os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "videos"), exist_ok=True)

    from app.api.courses import courses_bp
    from app.api.slides import slides_bp
    from app.api.videos import videos_bp
    from app.api.chat import chat_bp
    from app.api.knowledge_points import kp_bp
    from app.api.quizzes import quizzes_bp
    from app.api.dashboard import dashboard_bp

    app.register_blueprint(courses_bp, url_prefix="/api/courses")
    app.register_blueprint(slides_bp, url_prefix="/api/slides")
    app.register_blueprint(videos_bp, url_prefix="/api/videos")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(kp_bp, url_prefix="/api/knowledge-points")
    app.register_blueprint(quizzes_bp, url_prefix="/api/quizzes")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")

    # Health check endpoint
    @app.route("/health")
    def health_check():
        return {
            "status": "ok",
            "frontend_dir": frontend_dir,
            "frontend_exists": os.path.isdir(frontend_dir),
            "frontend_files": os.listdir(frontend_dir) if os.path.isdir(frontend_dir) else [],
        }

    # Serve frontend (index.html for SPA routing)
    app.logger.info(f"Frontend dir: {frontend_dir}, exists: {os.path.isdir(frontend_dir)}")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        if os.path.isdir(frontend_dir):
            return send_from_directory(frontend_dir, "index.html")
        return {"message": "Frontend not found", "frontend_dir": frontend_dir}, 404

    return app
