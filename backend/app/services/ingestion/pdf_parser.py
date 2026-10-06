"""
PDF parser using PyMuPDF.
Extracts:
  - Text per page (with page number)
  - Images/figures per page → captioned by VLM
  - Tables (heuristic: text blocks with grid-like structure)
"""
from __future__ import annotations
import asyncio
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PageContent:
    page_num: int            # 1-indexed
    text: str
    image_captions: list[str] = field(default_factory=list)
    raw_images: list[bytes] = field(default_factory=list)


async def parse_pdf(path: Path, caption_images: bool = True) -> list[PageContent]:
    """
    Parse a PDF file and return per-page content.
    Image captioning is done via VLM if caption_images=True.
    """
    import fitz  # PyMuPDF

    from app.services.llm.provider import get_vlm

    doc = fitz.open(str(path))
    pages: list[PageContent] = []

    vlm = get_vlm() if caption_images else None

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()

        # Extract images from this page
        image_list = page.get_images(full=True)
        raw_images: list[bytes] = []
        captions: list[str] = []

        for img_index, img_ref in enumerate(image_list):
            xref = img_ref[0]
            try:
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                # Only process images larger than 5KB (skip tiny icons)
                if len(img_bytes) > 5000:
                    raw_images.append(img_bytes)
            except Exception as e:
                logger.warning(f"Failed to extract image xref={xref}: {e}")

        if raw_images and vlm:
            caption_tasks = [
                _caption_image(vlm, img, page_num + 1, i)
                for i, img in enumerate(raw_images)
            ]
            captions = await asyncio.gather(*caption_tasks)

        pages.append(PageContent(
            page_num=page_num + 1,
            text=text,
            image_captions=captions,
            raw_images=raw_images,
        ))
        logger.debug(f"PDF page {page_num + 1}: {len(text)} chars, {len(raw_images)} images")

    doc.close()
    return pages


async def _caption_image(vlm, img_bytes: bytes, page_num: int, img_idx: int) -> str:
    """Caption a single image using the VLM."""
    from tenacity import retry, stop_after_attempt, wait_exponential

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _call():
        response = await vlm.generate(
            prompt=(
                "You are analyzing an image extracted from a textbook or lecture slide (page "
                f"{page_num}, figure {img_idx + 1}). "
                "Describe what is shown: if it's a diagram, explain its structure and key concepts; "
                "if it's a graph/chart, describe axes, trends, and values; "
                "if it's code, transcribe and explain it; "
                "if it's a photo or illustration, describe it. "
                "Be concise but thorough (2-5 sentences). Focus on information a student would need."
            ),
            images=[img_bytes],
            max_tokens=512,
            temperature=0.1,
        )
        return response.text.strip()

    try:
        return await _call()
    except Exception as e:
        logger.error(f"Image captioning failed (page {page_num}, img {img_idx}): {e}")
        return f"[Figure {img_idx + 1} on page {page_num} — captioning failed]"
