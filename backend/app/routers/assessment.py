"""
Assessment router.
Generate, submit, and report on assessments.
"""
from __future__ import annotations
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.assessment import Assessment, AssessmentAnswer, Question
from app.models.learner import ConceptMastery
from app.services.assessment.adaptive import build_assessment
from app.services.learner.model import update_after_answer, get_learner_summary
from app.services.llm.provider import get_llm
from app.utils.citation import make_citation_url

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


class GenerateRequest(BaseModel):
    student_id: str
    n_questions: int = 10
    qtype: str = "mcq"       # mcq | short | numerical | mixed
    scope: dict | None = None
    adaptive: bool = True


class SubmitRequest(BaseModel):
    assessment_id: str
    answers: list[dict]   # [{question_id, student_answer}]


@router.post("/generate")
async def generate_assessment(req: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """Generate an adaptive assessment."""
    try:
        assessment = await build_assessment(
            db=db,
            student_id=req.student_id,
            n_questions=req.n_questions,
            qtype=req.qtype,
            scope=req.scope,
            adaptive=req.adaptive,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Return assessment with questions (no answers)
    questions = []
    for qid in assessment.question_ids:
        q = await db.get(Question, qid)
        if q:
            q_data = {
                "id": q.id,
                "stem": q.stem,
                "qtype": q.qtype,
                "difficulty": q.difficulty,
                "source_location": q.source_location,
            }
            if q.qtype == "mcq" and q.choices:
                # Don't send correct flag
                q_data["choices"] = [{"id": c["id"], "text": c["text"]} for c in q.choices]
            questions.append(q_data)

    return {
        "assessment_id": assessment.id,
        "title": assessment.title,
        "questions": questions,
    }


@router.post("/submit")
async def submit_assessment(req: SubmitRequest, db: AsyncSession = Depends(get_db)):
    """Submit answers and get graded results."""
    assessment = await db.get(Assessment, req.assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    if assessment.status == "submitted":
        raise HTTPException(400, "Assessment already submitted")

    student_id = assessment.student_id
    llm = get_llm()
    graded: list[dict] = []
    total_correct = 0

    for ans in req.answers:
        qid = ans.get("question_id")
        student_answer = ans.get("student_answer", "")
        q = await db.get(Question, qid)
        if not q:
            continue

        # Grade
        correct, feedback = await _grade_answer(q, student_answer, llm)
        if correct:
            total_correct += 1

        # Update learner model
        concept_id = q.concept_id or q.topic_id or "general"
        await update_after_answer(
            db=db,
            student_id=student_id,
            concept_id=concept_id,
            correct=correct,
            session_id=req.assessment_id,
            question_text=q.stem,
            answer_text=student_answer,
        )

        # Save answer
        aa = AssessmentAnswer(
            id=str(uuid.uuid4()),
            assessment_id=req.assessment_id,
            question_id=qid,
            student_answer=student_answer,
            correct=correct,
            feedback=feedback,
            citations=[{"source_unit_id": q.source_unit_id, "location": q.source_location}] if q.source_unit_id else [],
        )
        db.add(aa)

        graded.append({
            "question_id": qid,
            "correct": correct,
            "correct_answer": q.answer,
            "explanation": q.explanation,
            "feedback": feedback,
            "citation_url": make_citation_url(
                q.source_unit_id or "", "pdf", q.source_location or "p1"
            ) if q.source_location else None,
        })

    score = total_correct / max(len(req.answers), 1)

    # Build report
    learner_state = await get_learner_summary(db, student_id)
    report = {
        "score": score,
        "total": len(req.answers),
        "correct": total_correct,
        "weak_topics": learner_state.get("weak_concepts", [])[:5],
        "recommendations": _generate_recommendations(score, learner_state),
    }

    assessment.status = "submitted"
    assessment.score = score
    assessment.report = report
    assessment.submitted_at = datetime.utcnow()
    await db.commit()

    return {
        "assessment_id": req.assessment_id,
        "score": score,
        "graded": graded,
        "report": report,
    }


@router.get("/{assessment_id}/report")
async def get_report(assessment_id: str, db: AsyncSession = Depends(get_db)):
    """Get the post-assessment report."""
    a = await db.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(404, "Assessment not found")
    return a.report or {"message": "Assessment not yet submitted"}


@router.get("/history")
async def get_history(student_id: str, db: AsyncSession = Depends(get_db)):
    """List assessment history for a student."""
    result = await db.execute(
        select(Assessment)
        .where(Assessment.student_id == student_id)
        .order_by(Assessment.created_at.desc())
    )
    assessments = result.scalars().all()
    return [
        {
            "id": a.id,
            "title": a.title,
            "status": a.status,
            "score": a.score,
            "n_questions": len(a.question_ids),
            "created_at": a.created_at.isoformat(),
        }
        for a in assessments
    ]


async def _grade_answer(question: Question, student_answer: str, llm) -> tuple[bool, str]:
    """Grade a student answer and return (correct, feedback)."""
    if question.qtype == "mcq":
        # Direct comparison
        correct = student_answer.strip().upper()[:1] == question.answer.strip().upper()[:1]
        feedback = (
            f"Correct! {question.explanation}" if correct
            else f"Incorrect. The correct answer is {question.answer}. {question.explanation}"
        )
        return correct, feedback

    # For short/numerical: LLM grading
    prompt = f"""Grade this student answer to the question.

Question: {question.stem}
Correct Answer: {question.answer}
Student Answer: {student_answer}

Is the student's answer correct or substantially correct? 
Reply with JSON: {{"correct": true/false, "feedback": "brief personalized feedback"}}"""

    try:
        response = await llm.generate(prompt, max_tokens=200, temperature=0.0)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        import json
        data = json.loads(text)
        return bool(data.get("correct", False)), data.get("feedback", "")
    except Exception:
        # Fallback: case-insensitive exact match
        correct = student_answer.strip().lower() == question.answer.strip().lower()
        return correct, question.explanation or ""


def _generate_recommendations(score: float, learner_state: dict) -> list[str]:
    recs = []
    if score < 0.5:
        recs.append("Review foundational concepts before attempting harder questions.")
    weak = learner_state.get("weak_concepts", [])[:3]
    if weak:
        recs.append(f"Focus on these weak areas: {', '.join(weak)}")
    due = learner_state.get("due_for_review", [])[:2]
    if due:
        recs.append(f"These concepts are due for review: {', '.join(due)}")
    if score > 0.8:
        recs.append("Excellent performance! Try harder questions or explore advanced topics.")
    return recs
