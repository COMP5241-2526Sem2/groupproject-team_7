from app import db
from datetime import datetime, timezone


class Quiz(db.Model):
    __tablename__ = "quizzes"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    knowledge_point_id = db.Column(
        db.Integer, db.ForeignKey("knowledge_points.id"), nullable=True
    )
    question = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON, nullable=False)  # ["A. ...", "B. ...", ...]
    correct_answer = db.Column(db.String(10), nullable=False)
    explanation = db.Column(db.Text, default="")
    video_timestamp = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    attempts = db.relationship("QuizAttempt", backref="quiz", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "course_id": self.course_id,
            "knowledge_point_id": self.knowledge_point_id,
            "question": self.question,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "video_timestamp": self.video_timestamp,
        }


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    selected_answer = db.Column(db.String(10), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "quiz_id": self.quiz_id,
            "selected_answer": self.selected_answer,
            "is_correct": self.is_correct,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
