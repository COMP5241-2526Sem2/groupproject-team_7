from datetime import datetime, timezone

from app import db


class VideoTranscript(db.Model):
    __tablename__ = "video_transcripts"

    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False)
    segment_index = db.Column(db.Integer, nullable=False, default=0)
    start_time = db.Column(db.Float, nullable=False, default=0)
    end_time = db.Column(db.Float, nullable=False, default=0)
    text = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "video_id": self.video_id,
            "segment_index": self.segment_index,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "text": self.text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }