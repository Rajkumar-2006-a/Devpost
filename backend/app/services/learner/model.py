"""
Learner model manager.
Handles: mastery reads/writes, BKT updates, spaced-rep scheduling,
weak-area detection, and cold-start diagnostic onboarding.
"""
from __future__ import annotations
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learner import Student, ConceptMastery, InteractionHistory
from app.services.learner.bkt import BKTParams, update_mastery, compute_uncertainty, zpd_score
from app.services.learner.forgetting import next_review_date, items_due

logger = logging.getLogger(__name__)


async def get_or_create_mastery(
    db: AsyncSession,
    student_id: str,
    concept_id: str,
) -> ConceptMastery:
    """Get existing mastery record or create a default one."""
    record = await db.get(ConceptMastery, (student_id, concept_id))
    if record is None:
        record = ConceptMastery(student_id=student_id, concept_id=concept_id)
        db.add(record)
        await db.flush()
    return record


async def update_after_answer(
    db: AsyncSession,
    student_id: str,
    concept_id: str,
    correct: bool,
    session_id: str | None = None,
    question_text: str | None = None,
    answer_text: str | None = None,
    source_units: list[str] | None = None,
) -> ConceptMastery:
    """
    Update BKT mastery and spaced-rep schedule after a quiz answer.
    Also logs the interaction.
    """
    record = await get_or_create_mastery(db, student_id, concept_id)

    params = BKTParams(
        prior=record.mastery_prob,
        transit=record.transit,
        slip=record.slip,
        guess=record.guess,
    )

    new_mastery = update_mastery(record.mastery_prob, correct, params)
    record.mastery_prob = new_mastery
    record.n_attempts += 1
    if correct:
        record.n_correct += 1
    record.uncertainty = compute_uncertainty(new_mastery, record.n_attempts)

    # Update spaced rep
    now = datetime.utcnow()
    last = record.last_reviewed or now
    next_dt, new_stab = next_review_date(last, record.stability, correct, record.n_correct)
    record.last_reviewed = now
    record.next_review = next_dt
    record.stability = new_stab

    # Log interaction
    ih = InteractionHistory(
        student_id=student_id,
        session_id=session_id,
        interaction_type="quiz_answer",
        concept_id=concept_id,
        correct=1 if correct else 0,
        question_text=question_text,
        answer_text=answer_text,
        source_units=source_units or [],
    )
    db.add(ih)
    await db.flush()
    return record


async def get_weak_concepts(db: AsyncSession, student_id: str, limit: int = 10) -> list[dict]:
    """Return concepts sorted by mastery ascending (weakest first)."""
    result = await db.execute(
        select(ConceptMastery)
        .where(ConceptMastery.student_id == student_id)
        .order_by(ConceptMastery.mastery_prob.asc())
        .limit(limit)
    )
    records = result.scalars().all()
    return [
        {
            "concept_id": r.concept_id,
            "mastery_prob": r.mastery_prob,
            "uncertainty": r.uncertainty,
            "n_attempts": r.n_attempts,
            "next_review": r.next_review.isoformat() if r.next_review else None,
        }
        for r in records
    ]


async def get_learner_summary(db: AsyncSession, student_id: str) -> dict:
    """Full learner state summary for tutor context."""
    result = await db.execute(
        select(ConceptMastery).where(ConceptMastery.student_id == student_id)
    )
    records = result.scalars().all()

    weak = [r.concept_id for r in records if r.mastery_prob < 0.45]
    strong = [r.concept_id for r in records if r.mastery_prob > 0.75]
    due = items_due([
        {"concept_id": r.concept_id, "next_review": r.next_review, "stability": r.stability}
        for r in records
    ])

    return {
        "weak_concepts": weak[:10],
        "strong_concepts": strong[:5],
        "due_for_review": due[:10],
        "total_concepts": len(records),
        "average_mastery": sum(r.mastery_prob for r in records) / max(len(records), 1),
    }


async def select_next_concept(
    db: AsyncSession,
    student_id: str,
    candidate_concept_ids: list[str],
) -> str | None:
    """
    ZPD-based adaptive concept selection.
    Returns the concept_id with the highest ZPD score.
    """
    if not candidate_concept_ids:
        return None

    scores: list[tuple[str, float]] = []
    for cid in candidate_concept_ids:
        record = await get_or_create_mastery(db, student_id, cid)
        score = zpd_score(record.mastery_prob, record.uncertainty)
        scores.append((cid, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[0][0] if scores else None
