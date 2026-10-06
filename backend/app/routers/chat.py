"""
Chat router.
Handles tutor chat sessions with source grounding.
"""
from __future__ import annotations
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.learner import InteractionHistory
from app.services.chat.tutor import answer, answer_outside_knowledge
from app.services.learner.model import get_learner_summary

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    student_id: str
    message: str
    session_id: str | None = None
    source_ids: list[str] | None = None
    topic_ids: list[str] | None = None
    request_outside_knowledge: bool = False


@router.post("")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Send a message and get a grounded tutor response."""
    session_id = req.session_id or str(uuid.uuid4())

    # Get session history (last 10 turns)
    hist_result = await db.execute(
        select(InteractionHistory)
        .where(
            InteractionHistory.student_id == req.student_id,
            InteractionHistory.session_id == session_id,
            InteractionHistory.interaction_type == "chat",
        )
        .order_by(InteractionHistory.ts.desc())
        .limit(10)
    )
    history_records = list(reversed(hist_result.scalars().all()))
    session_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": r.question_text or r.answer_text or ""}
        for i, r in enumerate(history_records)
    ]

    # Get learner state
    learner_state = await get_learner_summary(db, req.student_id)

    # Generate answer
    response = await answer(
        query=req.message,
        student_id=req.student_id,
        session_history=session_history,
        learner_state=learner_state,
        source_ids=req.source_ids,
        topic_ids=req.topic_ids,
    )

    # If refused and user wants outside knowledge
    outside_knowledge_answer = None
    if response.refused and req.request_outside_knowledge:
        outside_knowledge_answer = await answer_outside_knowledge(req.message)

    # Log interaction
    ih = InteractionHistory(
        student_id=req.student_id,
        session_id=session_id,
        interaction_type="chat",
        question_text=req.message,
        answer_text=response.answer,
        source_units=response.retrieved_units,
    )
    db.add(ih)
    await db.commit()

    return {
        "session_id": session_id,
        "answer": response.answer,
        "refused": response.refused,
        "outside_knowledge": outside_knowledge_answer,
        "citations": [
            {
                "index": c.index,
                "unit_id": c.unit_id,
                "source_id": c.source_id,
                "source_type": c.source_type,
                "location": c.location,
                "title": c.title,
                "snippet": c.snippet,
                "url": c.url,
            }
            for c in response.citations
        ],
    }


@router.get("/sessions")
async def list_sessions(student_id: str, db: AsyncSession = Depends(get_db)):
    """List chat sessions for a student."""
    result = await db.execute(
        select(
            InteractionHistory.session_id,
            InteractionHistory.ts,
        )
        .where(
            InteractionHistory.student_id == student_id,
            InteractionHistory.interaction_type == "chat",
            InteractionHistory.session_id.isnot(None),
        )
        .order_by(InteractionHistory.ts.desc())
    )
    seen = set()
    sessions = []
    for row in result.all():
        sid = row.session_id
        if sid and sid not in seen:
            seen.add(sid)
            sessions.append({"session_id": sid, "last_message_at": row.ts.isoformat()})
    return sessions


@router.get("/history/{session_id}")
async def get_history(session_id: str, student_id: str, db: AsyncSession = Depends(get_db)):
    """Get all turns for a session."""
    result = await db.execute(
        select(InteractionHistory)
        .where(
            InteractionHistory.student_id == student_id,
            InteractionHistory.session_id == session_id,
        )
        .order_by(InteractionHistory.ts.asc())
    )
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "question": r.question_text,
            "answer": r.answer_text,
            "ts": r.ts.isoformat(),
        }
        for r in records
    ]
