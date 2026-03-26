from app import db
from datetime import datetime, timezone


class VideoTranscript(db.Model):
    """Stores ASR transcript segments for a video with timestamps."""

    __tablename__ = "video_transcripts"

    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False)
    segment_index = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Float, nullable=False)  # seconds
    end_time = db.Column(db.Float, nullable=False)  # seconds
    text = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.LargeBinary, nullable=True)  # serialized float32 array

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "video_id": self.video_id,
            "segment_index": self.segment_index,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "text": self.text,
        }
