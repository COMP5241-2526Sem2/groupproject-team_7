from app import db
from datetime import datetime, timezone


class Slide(db.Model):
    __tablename__ = "slides"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # pdf, ppt, pptx
    file_path = db.Column(db.String(500), nullable=False)
    total_pages = db.Column(db.Integer, default=0)
    processed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    pages = db.relationship("SlidePage", backref="slide", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "course_id": self.course_id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "total_pages": self.total_pages,
            "processed": self.processed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "pages": [p.to_dict() for p in self.pages],
        }


class SlidePage(db.Model):
    __tablename__ = "slide_pages"

    id = db.Column(db.Integer, primary_key=True)
    slide_id = db.Column(db.Integer, db.ForeignKey("slides.id"), nullable=False)
    page_number = db.Column(db.Integer, nullable=False)
    content_text = db.Column(db.Text, default="")
    thumbnail_path = db.Column(db.String(500), default="")
    embedding = db.Column(db.LargeBinary, nullable=True)  # serialized float32 array

    knowledge_points = db.relationship(
        "KnowledgePoint", backref="slide_page", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "page_number": self.page_number,
            "content_text": self.content_text,
            "thumbnail_path": self.thumbnail_path,
            "knowledge_points": [kp.to_dict() for kp in self.knowledge_points],
        }
