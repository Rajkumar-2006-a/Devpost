"""
Knowledge base router.
Topics, prerequisite graph, unit search.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import KnowledgeUnit, Topic, Prerequisite
from app.services.knowledge.vector_store import get_vector_store

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/topics")
async def get_topics(student_id: str, db: AsyncSession = Depends(get_db)):
    """Return topic hierarchy for a student."""
    result = await db.execute(
        select(Topic).where(Topic.student_id == student_id).order_by(Topic.level, Topic.name)
    )
    topics = result.scalars().all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "level": t.level,
            "parent_id": t.parent_id,
            "source_id": t.source_id,
        }
        for t in topics
    ]


@router.get("/graph")
async def get_prerequisite_graph(student_id: str, db: AsyncSession = Depends(get_db)):
    """Return nodes + edges for the React Flow topic/prerequisite graph."""
    topics_result = await db.execute(
        select(Topic).where(Topic.student_id == student_id)
    )
    topics = topics_result.scalars().all()

    prereqs_result = await db.execute(select(Prerequisite))
    prereqs = prereqs_result.scalars().all()

    topic_ids = {t.id for t in topics}
    nodes = [
        {
            "id": t.id,
            "data": {"label": t.name, "level": t.level, "description": t.description},
            "type": "topicNode",
        }
        for t in topics
    ]
    edges = [
        {
            "id": f"{p.from_id}-{p.to_id}",
            "source": p.from_id,
            "target": p.to_id,
            "type": "prerequisite",
        }
        for p in prereqs
        if p.from_id in topic_ids and p.to_id in topic_ids
    ]
    return {"nodes": nodes, "edges": edges}


@router.get("/search")
async def search_knowledge(
    q: str,
    student_id: str,
    topic_id: str | None = None,
    source_id: str | None = None,
    top_k: int = Query(default=5, le=20),
):
    """Semantic search across the knowledge base."""
    vs = get_vector_store()
    where = {"student_id": {"$eq": student_id}}
    if source_id:
        where = {"$and": [where, {"source_id": {"$eq": source_id}}]}

    results = await vs.hybrid_search(q, top_k=top_k, where=where)

    if topic_id:
        results = [r for r in results if topic_id in r.topic_ids]

    from app.utils.citation import make_citation_url
    return [
        {
            "unit_id": r.unit_id,
            "source_id": r.source_id,
            "source_type": r.source_type,
            "location": r.location,
            "text": r.text,
            "modality": r.modality,
            "score": r.score,
            "citation_url": make_citation_url(r.source_id, r.source_type, r.location),
        }
        for r in results
    ]


@router.get("/unit/{unit_id}")
async def get_unit(unit_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single knowledge unit."""
    unit = await db.get(KnowledgeUnit, unit_id)
    if not unit:
        from fastapi import HTTPException
        raise HTTPException(404, "Unit not found")
    from app.utils.citation import make_citation_url
    return {
        "unit_id": unit.unit_id,
        "source_id": unit.source_id,
        "source_type": unit.source_type,
        "location": unit.location,
        "text": unit.text,
        "modality": unit.modality,
        "topic_ids": unit.topic_ids,
        "concept_ids": unit.concept_ids,
        "citation_url": make_citation_url(unit.source_id, unit.source_type, unit.location),
    }
