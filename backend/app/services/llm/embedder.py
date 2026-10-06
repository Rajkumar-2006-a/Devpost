"""
Unified embedding interface.
Uses Google text-embedding-004 (primary) or OpenAI text-embedding-3-small.
Returns List[float] for a single text, or List[List[float]] for a batch.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GoogleEmbedder:
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=settings.google_api_key)
        self._model = settings.embedding_model
        self._genai = genai

    async def embed(self, text: str) -> list[float]:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._genai.embed_content(
                model=self._model,
                content=text,
                task_type="retrieval_document",
            ),
        )
        return result["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results = await asyncio.gather(*[self.embed(t) for t in texts])
        return list(results)

    async def embed_query(self, text: str) -> list[float]:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._genai.embed_content(
                model=self._model,
                content=text,
                task_type="retrieval_query",
            ),
        )
        return result["embedding"]


class OpenAIEmbedder:
    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = "text-embedding-3-small"

    async def embed(self, text: str) -> list[float]:
        resp = await self.client.embeddings.create(model=self._model, input=text)
        return resp.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        resp = await self.client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in resp.data]

    async def embed_query(self, text: str) -> list[float]:
        return await self.embed(text)


def get_embedder() -> GoogleEmbedder | OpenAIEmbedder:
    if settings.llm_provider == "google":
        return GoogleEmbedder()
    return OpenAIEmbedder()
