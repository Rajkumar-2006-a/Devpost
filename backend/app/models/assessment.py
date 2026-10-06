"""
Assessment ORM models: Question, Assessment, AssessmentAnswer.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, Float, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Question(Base):
    """
    A generated question with full provenance.
    Must be verified and tagged before being usable in an assessment.
    """
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    topic_id: Mapped[str | None] = mapped_column(String, nullable=True)
    concept_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_unit_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_location: Mapped[str | None] = mapped_column(String, nullable=True)   # "p42" | "s7" | "0:34-1:12"
    qtype: Mapped[str] = mapped_column(String)                         # mcq | short | numerical
    difficulty: Mapped[int] = mapped_column(Integer, default=3)        # 1-5
    stem: Mapped[str] = mapped_column(Text)
    choices: Mapped[list | None] = mapped_column(JSON, nullable=True)  # MCQ choices [{id, text, correct}]
    answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Assessment(Base):
    """An assessment session (quiz or exam) for a student."""
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, default="Untitled Assessment")
    scope: Mapped[dict | None] = mapped_column(JSON, nullable=True)    # {topic_ids, source_ids, page_range}
    question_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="pending")     # pending|active|submitted
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # post-assessment report
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    answers: Mapped[list["AssessmentAnswer"]] = relationship(
        "AssessmentAnswer", back_populates="assessment", cascade="all, delete-orphan"
    )


class AssessmentAnswer(Base):
    __tablename__ = "assessment_answers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    assessment_id: Mapped[str] = mapped_column(String, ForeignKey("assessments.id", ondelete="CASCADE"))
    question_id: Mapped[str] = mapped_column(String, ForeignKey("questions.id"))
    student_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list] = mapped_column(JSON, default=list)

    assessment: Mapped[Assessment] = relationship("Assessment", back_populates="answers")
