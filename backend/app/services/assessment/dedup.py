"""
Question deduplication.
Checks a new question against the student's existing question bank
using cosine similarity of embeddings. Rejects near-duplicates (≥0.85).
"""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from app.services.llm.embedder import get_embedder

if TYPE_CHECKING:
    from app.services.assessment.generator import GeneratedQuestion

logger = logging.getLogger(__name__)

DEDUP_THRESHOLD = 0.85


async def is_duplicate(
    new_stem: str,
    existing_stems: list[str],
) -> bool:
    """
    Return True if new_stem is too similar to any existing question.
    Uses cosine similarity on embeddings.
    """
    if not existing_stems:
        return False

    embedder = get_embedder()
    all_texts = [new_stem] + existing_stems
    embeddings = await embedder.embed_batch(all_texts)

    new_emb = embeddings[0]
    existing_embs = embeddings[1:]

    for existing_emb in existing_embs:
        sim = _cosine(new_emb, existing_emb)
        if sim >= DEDUP_THRESHOLD:
            logger.info(f"Duplicate detected (sim={sim:.3f} ≥ {DEDUP_THRESHOLD})")
            return True

    return False


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
