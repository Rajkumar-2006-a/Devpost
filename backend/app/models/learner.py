"""
Learner ORM models: Student, ConceptMastery, InteractionHistory.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, Text, DateTime, Date, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    exam_date: Mapped[str | None] = mapped_column(String, nullable=True)   # ISO date string
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    prior_knowledge: Mapped[str | None] = mapped_column(Text, nullable=True)
    onboarding_done: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    mastery_records: Mapped[list["ConceptMastery"]] = relationship(
        "ConceptMastery", back_populates="student", cascade="all, delete-orphan"
    )
    interactions: Mapped[list["InteractionHistory"]] = relationship(
        "InteractionHistory", back_populates="student", cascade="all, delete-orphan"
    )


class ConceptMastery(Base):
    __tablename__ = "concept_mastery"

    student_id: Mapped[str] = mapped_column(String, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    concept_id: Mapped[str] = mapped_column(String, primary_key=True)
    mastery_prob: Mapped[float] = mapped_column(Float, default=0.30)   # BKT P(L)
    uncertainty: Mapped[float] = mapped_column(Float, default=0.50)    # epistemic uncertainty
    slip: Mapped[float] = mapped_column(Float, default=0.10)           # BKT P(S)
    guess: Mapped[float] = mapped_column(Float, default=0.25)          # BKT P(G)
    transit: Mapped[float] = mapped_column(Float, default=0.10)        # BKT P(T)
    n_attempts: Mapped[int] = mapped_column(Integer, default=0)
    n_correct: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_review: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)   # spaced rep
    stability: Mapped[float] = mapped_column(Float, default=1.0)       # SM2 stability factor

    student: Mapped[Student] = relationship("Student", back_populates="mastery_records")


class InteractionHistory(Base):
    __tablename__ = "interaction_history"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id: Mapped[str] = mapped_column(String, ForeignKey("students.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    interaction_type: Mapped[str] = mapped_column(String)  # quiz_answer | chat | diagnostic
    concept_id: Mapped[str | None] = mapped_column(String, nullable=True)
    topic_id: Mapped[str | None] = mapped_column(String, nullable=True)
    correct: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 1/0/None
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_units: Mapped[list] = mapped_column(JSON, default=list)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped[Student] = relationship("Student", back_populates="interactions")
