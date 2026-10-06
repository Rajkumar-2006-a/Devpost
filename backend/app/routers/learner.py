"""
Learner model router.
Exposes mastery state, schedule, weak areas, and onboarding.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.learner import Student, ConceptMastery
from app.services.learner.model import get_weak_concepts, get_learner_summary
from app.services.learner.forgetting import items_due, retention_prob
from datetime import datetime

router = APIRouter(prefix="/api/learner", tags=["learner"])


class OnboardRequest(BaseModel):
    name: str
    exam_date: str | None = None
    goals: str | None = None
    prior_knowledge: str | None = None


class StudentResponse(BaseModel):
    id: str
    name: str
    exam_date: str | None
    goals: str | None
    onboarding_done: bool


@router.post("/onboard")
async def onboard(req: OnboardRequest, db: AsyncSession = Depends(get_db)):
    """Create or onboard a new student."""
    student = Student(
        id=str(uuid.uuid4()),
        name=req.name,
        exam_date=req.exam_date,
        goals=req.goals,
        prior_knowledge=req.prior_knowledge,
        onboarding_done=True,
    )
    db.add(student)
    await db.commit()
    return {"student_id": student.id, "name": student.name}


@router.get("/{student_id}/model")
async def get_model(student_id: str, db: AsyncSession = Depends(get_db)):
    """Full mastery state for a student."""
    result = await db.execute(
        select(ConceptMastery).where(ConceptMastery.student_id == student_id)
    )
    records = result.scalars().all()

    now = datetime.utcnow()
    return {
        "student_id": student_id,
        "concepts": [
            {
                "concept_id": r.concept_id,
                "mastery_prob": round(r.mastery_prob, 3),
                "uncertainty": round(r.uncertainty, 3),
                "n_attempts": r.n_attempts,
                "n_correct": r.n_correct,
                "last_reviewed": r.last_reviewed.isoformat() if r.last_reviewed else None,
                "next_review": r.next_review.isoformat() if r.next_review else None,
                "retention": round(
                    retention_prob(r.last_reviewed, r.stability, now) if r.last_reviewed else 1.0,
                    3,
                ),
            }
            for r in records
        ],
    }


@router.get("/{student_id}/schedule")
async def get_schedule(student_id: str, db: AsyncSession = Depends(get_db)):
    """Get review schedule: concepts due now + upcoming."""
    result = await db.execute(
        select(ConceptMastery).where(ConceptMastery.student_id == student_id)
    )
    records = result.scalars().all()
    now = datetime.utcnow()

    due_now = [r for r in records if r.next_review and r.next_review <= now]
    upcoming = sorted(
        [r for r in records if r.next_review and r.next_review > now],
        key=lambda r: r.next_review,
    )[:10]

    return {
        "due_now": [
            {"concept_id": r.concept_id, "mastery": round(r.mastery_prob, 3)}
            for r in due_now
        ],
        "upcoming": [
            {
                "concept_id": r.concept_id,
                "next_review": r.next_review.isoformat(),
                "days_until": (r.next_review - now).days,
            }
            for r in upcoming
        ],
    }


@router.get("/{student_id}/weak-areas")
async def get_weak_areas(student_id: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Return weakest concepts for targeted study."""
    return await get_weak_concepts(db, student_id, limit)


@router.get("/{student_id}/summary")
async def get_summary(student_id: str, db: AsyncSession = Depends(get_db)):
    """Compact learner summary for tutor context."""
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "Student not found")
    summary = await get_learner_summary(db, student_id)
    return {
        "student_id": student_id,
        "name": student.name,
        "exam_date": student.exam_date,
        "goals": student.goals,
        **summary,
    }


@router.get("/students")
async def list_students(db: AsyncSession = Depends(get_db)):
    """List all students (for demo/dev purposes)."""
    result = await db.execute(select(Student).order_by(Student.created_at.desc()))
    students = result.scalars().all()
    return [
        {"id": s.id, "name": s.name, "exam_date": s.exam_date, "created_at": s.created_at.isoformat()}
        for s in students
    ]
