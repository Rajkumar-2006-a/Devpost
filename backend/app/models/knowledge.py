"""
Knowledge ORM models: KnowledgeUnit, Topic, Prerequisite.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KnowledgeUnit(Base):
    __tablename__ = "knowledge_units"

    unit_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(String, ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String)          # video | pdf | pptx
    location: Mapped[str] = mapped_column(String)              # "p42" | "s7" | "0:34-1:12"
    text: Mapped[str] = mapped_column(Text, nullable=False)
    modality: Mapped[str] = mapped_column(String, default="text")  # text | image_caption | transcript
    topic_ids: Mapped[list] = mapped_column(JSON, default=list)
    concept_ids: Mapped[list] = mapped_column(JSON, default=list)
    embedding_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source: Mapped["Source"] = relationship("Source", back_populates="units")  # noqa: F821


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str | None] = mapped_column(String, ForeignKey("sources.id", ondelete="CASCADE"), nullable=True)
    student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[str | None] = mapped_column(String, ForeignKey("topics.id"), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=0)  # 0=topic,1=subtopic,2=concept
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source: Mapped["Source"] = relationship("Source", back_populates="topics")  # noqa: F821
    children: Mapped[list["Topic"]] = relationship("Topic", back_populates="parent")
    parent: Mapped["Topic | None"] = relationship("Topic", back_populates="children", remote_side="Topic.id")


class Prerequisite(Base):
    __tablename__ = "prerequisites"

    from_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    to_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    strength: Mapped[float] = mapped_column(default=1.0)  # 0-1 confidence that from_id requires to_id
