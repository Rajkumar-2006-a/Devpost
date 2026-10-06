"""
Adaptive assessment orchestrator.
Selects concepts via ZPD, retrieves units, generates/verifies/deduplicates
questions, and assembles an assessment.
"""
from __future__ import annotations
import logging
import random
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Question, Assessment
from app.models.knowledge import KnowledgeUnit
from app.services.assessment.generator import generate_question
from app.services.assessment.verifier import verify_question
from app.services.assessment.dedup import is_duplicate
from app.services.learner.model import select_next_concept, get_or_create_mastery
from app.services.knowledge.vector_store import get_vector_store, SearchResult

logger = logging.getLogger(__name__)

MAX_REGEN_ATTEMPTS = 3


async def build_assessment(
    db: AsyncSession,
    student_id: str,
    n_questions: int = 10,
    qtype: str = "mcq",       # mcq | short | numerical | mixed
    scope: dict | None = None,  # {topic_ids, source_ids}
    adaptive: bool = True,
) -> Assessment:
    """
    Build an assessment for a student.
    If adaptive=True, selects concepts via ZPD; else picks randomly.
    """
    scope = scope or {}
    topic_ids = scope.get("topic_ids", [])
    source_ids = scope.get("source_ids", [])

    # 1. Get all candidate units
    vs = get_vector_store()
    where = {"student_id": {"$eq": student_id}}
    if source_ids:
        where = {"$and": [where, {"source_id": {"$in": source_ids}}]}

    # Use a generic educational query to fetch diverse units
    candidate_results = await vs.hybrid_search(
        "concept definition explanation example",
        top_k=50,
        where=where,
    )

    if not candidate_results:
        raise ValueError("No knowledge units found for this scope. Please ingest materials first.")

    # 2. Get existing question stems for dedup
    existing_q_result = await db.execute(
        select(Question.stem).where(Question.student_id == student_id)
    )
    existing_stems = [row[0] for row in existing_q_result.all()]

    # 3. Get all concept IDs from units
    all_concept_ids = list({cid for r in candidate_results for cid in r.concept_ids})

    questions: list[Question] = []
    attempts = 0

    while len(questions) < n_questions and attempts < n_questions * MAX_REGEN_ATTEMPTS:
        attempts += 1

        # Select concept (adaptive or random)
        if adaptive and all_concept_ids:
            concept_id = await select_next_concept(db, student_id, all_concept_ids)
        else:
            concept_id = random.choice(all_concept_ids) if all_concept_ids else None

        # Find a unit for this concept
        matching_units = [r for r in candidate_results if concept_id in r.concept_ids] if concept_id else candidate_results
        if not matching_units:
            matching_units = candidate_results
        unit = random.choice(matching_units)

        # Determine question type
        if qtype == "mixed":
            actual_qtype = random.choice(["mcq", "short", "numerical"])
        else:
            actual_qtype = qtype

        # Determine difficulty based on mastery
        mastery_rec = await get_or_create_mastery(db, student_id, concept_id or "default")
        difficulty = _mastery_to_difficulty(mastery_rec.mastery_prob)

        # Generate
        gen_q = await generate_question(
            unit=unit,
            qtype=actual_qtype,
            difficulty=difficulty,
            topic_id=unit.topic_ids[0] if unit.topic_ids else None,
            concept_id=concept_id,
        )

        if gen_q is None:
            continue

        # Verify
        if not await verify_question(gen_q):
            logger.info("Question failed verification, regenerating...")
            continue

        # Dedup
        if await is_duplicate(gen_q.stem, existing_stems):
            continue

        # Persist
        q = Question(
            id=str(uuid.uuid4()),
            student_id=student_id,
            topic_id=gen_q.topic_id,
            concept_id=gen_q.concept_id,
            source_unit_id=gen_q.source_unit_id,
            source_location=gen_q.source_location,
            qtype=gen_q.qtype,
            difficulty=gen_q.difficulty,
            stem=gen_q.stem,
            choices=gen_q.choices,
            answer=gen_q.answer,
            explanation=gen_q.explanation,
            verified=True,
        )
        db.add(q)
        await db.flush()
        questions.append(q)
        existing_stems.append(gen_q.stem)

    if not questions:
        raise ValueError("Could not generate any questions after maximum attempts.")

    # Create Assessment
    assessment = Assessment(
        id=str(uuid.uuid4()),
        student_id=student_id,
        title=f"Adaptive Assessment ({len(questions)} questions)",
        scope=scope,
        question_ids=[q.id for q in questions],
        status="active",
    )
    db.add(assessment)
    await db.commit()
    return assessment


def _mastery_to_difficulty(mastery: float) -> int:
    """Map mastery probability to question difficulty 1-5."""
    if mastery < 0.2:
        return 1
    elif mastery < 0.4:
        return 2
    elif mastery < 0.6:
        return 3
    elif mastery < 0.8:
        return 4
    return 5
