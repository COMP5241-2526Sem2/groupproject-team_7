import os

from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_name="default"):
    from config import config as config_map

    app = Flask(__name__)
    app.config.from_object(config_map[config_name])

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)
    migrate.init_app(app, db)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "slides"), exist_ok=True)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "slides", "thumbnails"), exist_ok=True)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "videos"), exist_ok=True)

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

    return app
