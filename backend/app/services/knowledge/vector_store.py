"""
Vector store: ChromaDB wrapper with hybrid BM25 + dense retrieval.
Provides upsert, query, and metadata-filtered search.
"""
from __future__ import annotations
import logging
import uuid
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings as ChromaSettings
from rank_bm25 import BM25Okapi

from app.config import get_settings
from app.services.llm.embedder import get_embedder

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SearchResult:
    unit_id: str
    source_id: str
    source_type: str
    location: str
    text: str
    modality: str
    topic_ids: list[str]
    concept_ids: list[str]
    score: float    # higher is better (fused rank score)


class VectorStore:
    def __init__(self):
        self._client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._col = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = get_embedder()

    async def upsert(
        self,
        unit_id: str,
        text: str,
        metadata: dict,
    ) -> None:
        """Embed and upsert a single knowledge unit."""
        embedding = await self._embedder.embed(text)
        self._col.upsert(
            ids=[unit_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata],
        )

    async def upsert_batch(self, units: list[dict]) -> None:
        """
        Batch upsert.
        Each unit: {unit_id, text, metadata}
        """
        texts = [u["text"] for u in units]
        embeddings = await self._embedder.embed_batch(texts)
        self._col.upsert(
            ids=[u["unit_id"] for u in units],
            embeddings=embeddings,
            documents=texts,
            metadatas=[u["metadata"] for u in units],
        )

    async def hybrid_search(
        self,
        query: str,
        top_k: int | None = None,
        where: dict | None = None,
    ) -> list[SearchResult]:
        """
        Hybrid search: dense (Chroma) + BM25 sparse, fused via RRF.
        Returns top_k results sorted by fused score (descending).
        """
        top_k = top_k or settings.retrieval_top_k

        # 1. Dense retrieval
        query_emb = await self._embedder.embed_query(query)
        n_dense = min(top_k * 2, self._col.count() or 1)

        kwargs: dict = {"query_embeddings": [query_emb], "n_results": n_dense, "include": ["documents", "metadatas", "distances"]}
        if where:
            kwargs["where"] = where

        dense_res = self._col.query(**kwargs)
        ids = dense_res["ids"][0]
        docs = dense_res["documents"][0]
        metas = dense_res["metadatas"][0]
        dists = dense_res["distances"][0]   # cosine distance [0,2], lower = better

        # 2. BM25 sparse retrieval on retrieved corpus
        # Fetch all docs for BM25 (or use dense candidates as corpus)
        corpus_docs = docs
        tokenized_corpus = [d.lower().split() for d in corpus_docs]
        if tokenized_corpus:
            bm25 = BM25Okapi(tokenized_corpus)
            bm25_scores = bm25.get_scores(query.lower().split())
        else:
            bm25_scores = [0.0] * len(corpus_docs)

        # 3. RRF fusion
        # dense rank: sort by distance ascending (lower dist = better rank)
        dense_ranks = {uid: rank + 1 for rank, uid in enumerate(ids)}
        bm25_ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
        bm25_ranks = {ids[i]: rank + 1 for rank, i in enumerate(bm25_ranked)}

        k = 60   # RRF constant
        fused: dict[str, float] = {}
        for uid in ids:
            dr = dense_ranks.get(uid, len(ids) + 1)
            br = bm25_ranks.get(uid, len(ids) + 1)
            fused[uid] = 1 / (k + dr) + 1 / (k + br)

        # Sort by fused score descending
        sorted_ids = sorted(fused, key=lambda x: fused[x], reverse=True)[:top_k]

        id_to_meta = {ids[i]: metas[i] for i in range(len(ids))}
        id_to_doc = {ids[i]: docs[i] for i in range(len(ids))}

        results: list[SearchResult] = []
        for uid in sorted_ids:
            meta = id_to_meta.get(uid, {})
            results.append(SearchResult(
                unit_id=uid,
                source_id=meta.get("source_id", ""),
                source_type=meta.get("source_type", ""),
                location=meta.get("location", ""),
                text=id_to_doc.get(uid, ""),
                modality=meta.get("modality", "text"),
                topic_ids=_parse_list(meta.get("topic_ids", "")),
                concept_ids=_parse_list(meta.get("concept_ids", "")),
                score=fused[uid],
            ))
        return results

    def delete_by_source(self, source_id: str) -> None:
        """Remove all units belonging to a source."""
        self._col.delete(where={"source_id": source_id})

    def count(self) -> int:
        return self._col.count()


def _parse_list(value) -> list[str]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        import json
        try:
            return json.loads(value)
        except Exception:
            return [value] if value else []
    return []


# Singleton
_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
