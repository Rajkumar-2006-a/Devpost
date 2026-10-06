"""
RAG retrieval pipeline with reranking.
Returns top-K knowledge units for a query, along with a confidence score.
"""
from __future__ import annotations
import logging

from app.config import get_settings
from app.services.knowledge.vector_store import get_vector_store, SearchResult

logger = logging.getLogger(__name__)
settings = get_settings()


async def retrieve(
    query: str,
    student_id: str,
    top_k: int | None = None,
    topic_ids: list[str] | None = None,
    source_ids: list[str] | None = None,
) -> tuple[list[SearchResult], float]:
    """
    Retrieve relevant knowledge units for a query.
    Returns (results, max_score). max_score < threshold → refuse.
    """
    top_k = top_k or settings.retrieval_top_k
    vs = get_vector_store()

    # Build metadata filter
    where: dict | None = None
    filters = [{"student_id": {"$eq": student_id}}]

    if source_ids:
        filters.append({"source_id": {"$in": source_ids}})
    if topic_ids:
        # ChromaDB doesn't support list-in-list; filter post-retrieval
        pass

    if len(filters) == 1:
        where = filters[0]
    elif len(filters) > 1:
        where = {"$and": filters}

    results = await vs.hybrid_search(query, top_k=top_k * 2, where=where)

    # Post-filter by topic_ids if specified
    if topic_ids:
        results = [
            r for r in results
            if any(tid in r.topic_ids for tid in topic_ids)
        ]

    # Rerank with cross-encoder if available
    results = await _rerank(query, results)

    final = results[:settings.rerank_top_k]
    max_score = final[0].score if final else 0.0
    return final, max_score


async def _rerank(query: str, results: list[SearchResult]) -> list[SearchResult]:
    """
    Cross-encoder reranking.
    Falls back to fused score if transformers not available.
    """
    if not results:
        return results

    try:
        from sentence_transformers import CrossEncoder
        import asyncio

        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        pairs = [(query, r.text) for r in results]
        scores = await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.predict(pairs)
        )
        for i, r in enumerate(results):
            r.score = float(scores[i])
        results.sort(key=lambda x: x.score, reverse=True)
    except Exception as e:
        logger.warning(f"Cross-encoder reranking unavailable, using fused score: {e}")

    return results
