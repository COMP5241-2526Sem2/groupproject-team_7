from app import db
from datetime import datetime, timezone


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    slides = db.relationship("Slide", backref="course", lazy=True, cascade="all, delete-orphan")
    videos = db.relationship("Video", backref="course", lazy=True, cascade="all, delete-orphan")
    chat_messages = db.relationship("ChatMessage", backref="course", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "slides_count": len(self.slides),
            "videos_count": len(self.videos),
        }
