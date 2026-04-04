from app import db
from datetime import datetime, timezone


class Video(db.Model):
    __tablename__ = "videos"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.Float, default=0)  # seconds
    processed = db.Column(db.Boolean, default=False)
    uploader_role = db.Column(db.String(50), default='teacher')  # 'teacher' or 'student'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def is_external(self):
        return isinstance(self.file_path, str) and self.file_path.startswith(("http://", "https://"))

    def to_dict(self):
        external = self.is_external()
        return {
            "id": self.id,
            "course_id": self.course_id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "duration": self.duration,
            "processed": self.processed,
            "uploader_role": self.uploader_role,
            "source_type": "external" if external else "uploaded",
            "external_url": self.file_path if external else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
