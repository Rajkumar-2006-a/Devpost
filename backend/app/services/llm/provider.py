"""
Unified LLM / VLM provider interface.
Supports Google Gemini (primary) and OpenAI (fallback).
All callers use `get_llm()` and call `.generate(prompt, images=None)`.
"""
from __future__ import annotations
import base64
import logging
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMResponse:
    def __init__(self, text: str, raw: Any = None):
        self.text = text
        self.raw = raw

    def __str__(self) -> str:
        return self.text


class GeminiProvider:
    """Google Gemini via google-generativeai SDK."""

    def __init__(self, model: str):
        import google.generativeai as genai
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(model)
        self._model_name = model

    async def generate(self, prompt: str, images: list[bytes | Path] | None = None, **kwargs) -> LLMResponse:
        import google.generativeai as genai
        import asyncio

        parts: list[Any] = []

        if images:
            for img in images:
                if isinstance(img, Path):
                    img = img.read_bytes()
                parts.append({"mime_type": "image/jpeg", "data": base64.b64encode(img).decode()})

        parts.append(prompt)

        # google-generativeai is sync; run in thread pool
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.model.generate_content(
                parts,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=kwargs.get("max_tokens", 4096),
                    temperature=kwargs.get("temperature", 0.2),
                ),
            ),
        )
        return LLMResponse(text=response.text, raw=response)


class OpenAIProvider:
    """OpenAI ChatCompletion provider."""

    def __init__(self, model: str):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model_name = model

    async def generate(self, prompt: str, images: list[bytes | Path] | None = None, **kwargs) -> LLMResponse:
        messages: list[dict] = []
        if images:
            content: list[dict] = [{"type": "text", "text": prompt}]
            for img in images:
                if isinstance(img, Path):
                    img = img.read_bytes()
                b64 = base64.b64encode(img).decode()
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self._model_name,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.2),
        )
        return LLMResponse(text=response.choices[0].message.content, raw=response)


def get_llm() -> GeminiProvider | OpenAIProvider:
    """Return the configured LLM provider singleton."""
    if settings.llm_provider == "google":
        return GeminiProvider(settings.llm_model)
    return OpenAIProvider(settings.llm_model)


def get_vlm() -> GeminiProvider | OpenAIProvider:
    """Return the configured VLM provider (for image captioning)."""
    if settings.llm_provider == "google":
        return GeminiProvider(settings.vlm_model)
    return OpenAIProvider("gpt-4o")
