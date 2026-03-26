from app import db
from datetime import datetime, timezone


class KnowledgePoint(db.Model):
    __tablename__ = "knowledge_points"

    id = db.Column(db.Integer, primary_key=True)
    slide_page_id = db.Column(db.Integer, db.ForeignKey("slide_pages.id"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    content = db.Column(db.Text, default="")
    video_timestamp = db.Column(db.Float, nullable=True)  # seconds into video
    confidence = db.Column(db.Float, default=0.0)  # alignment confidence score

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "slide_page_id": self.slide_page_id,
            "slide_id": self.slide_page.slide_id if self.slide_page else None,
            "page_number": self.slide_page.page_number if self.slide_page else None,
            "video_id": self.video_id,
            "title": self.title,
            "content": self.content,
            "video_timestamp": self.video_timestamp,
            "confidence": self.confidence,
        }
