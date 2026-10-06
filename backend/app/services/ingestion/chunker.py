"""
Text chunker: converts parsed pages/slides/transcript into KnowledgeUnit records.
Uses a sliding window of ~CHUNK_SIZE tokens with CHUNK_OVERLAP overlap.
Respects sentence boundaries (splits on '. ', '! ', '? ', '\n\n').
"""
from __future__ import annotations
import re
import uuid
import logging
from dataclasses import dataclass

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Simple word-based tokenisation (avoids loading a tokenizer just for chunking)
def _approx_tokens(text: str) -> int:
    return len(text.split())


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """
    Split text into overlapping chunks of approximately chunk_size tokens.
    """
    chunk_size = chunk_size or settings.chunk_size_tokens
    overlap = overlap or settings.chunk_overlap_tokens

    sentences = _split_sentences(text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sent in sentences:
        sent_len = _approx_tokens(sent)
        if current_len + sent_len > chunk_size and current:
            chunks.append(" ".join(current))
            # Keep overlap sentences
            overlap_sentences: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                l = _approx_tokens(s)
                if overlap_len + l > overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_len += l
            current = overlap_sentences
            current_len = overlap_len
        current.append(sent)
        current_len += sent_len

    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if c.strip()]


@dataclass
class RawUnit:
    """Intermediate unit before embedding/DB insertion."""
    source_id: str
    source_type: str     # video | pdf | pptx
    location: str        # "p42" | "s7" | "1:34-2:12"
    text: str
    modality: str        # text | image_caption | transcript


def units_from_pdf_pages(source_id: str, pages) -> list[RawUnit]:
    """Convert PDF PageContent list into RawUnit list."""
    units: list[RawUnit] = []
    for page in pages:
        location = f"p{page.page_num}"
        if page.text:
            for chunk in chunk_text(page.text):
                units.append(RawUnit(
                    source_id=source_id,
                    source_type="pdf",
                    location=location,
                    text=chunk,
                    modality="text",
                ))
        for i, caption in enumerate(page.image_captions):
            if caption:
                units.append(RawUnit(
                    source_id=source_id,
                    source_type="pdf",
                    location=location,
                    text=f"[Figure {i+1}, page {page.page_num}] {caption}",
                    modality="image_caption",
                ))
    return units


def units_from_pptx_slides(source_id: str, slides) -> list[RawUnit]:
    """Convert PPTX SlideContent list into RawUnit list."""
    units: list[RawUnit] = []
    for slide in slides:
        location = f"s{slide.slide_num}"
        full_text = f"{slide.title}\n{slide.body_text}\n{slide.notes}".strip()
        if full_text:
            for chunk in chunk_text(full_text):
                units.append(RawUnit(
                    source_id=source_id,
                    source_type="pptx",
                    location=location,
                    text=chunk,
                    modality="text",
                ))
        for i, caption in enumerate(slide.image_captions):
            if caption:
                units.append(RawUnit(
                    source_id=source_id,
                    source_type="pptx",
                    location=location,
                    text=f"[Slide {slide.slide_num}, image {i+1}] {caption}",
                    modality="image_caption",
                ))
    return units


def units_from_video(source_id: str, video_content) -> list[RawUnit]:
    """Convert VideoContent into RawUnit list."""
    units: list[RawUnit] = []

    # Group transcript segments into chunks
    seg_buffer: list = []
    buf_tokens = 0
    chunk_size = settings.chunk_size_tokens

    def _flush(segs):
        if not segs:
            return
        start = segs[0].start
        end = segs[-1].end
        text = " ".join(s.text for s in segs)
        start_str = _ts(start)
        end_str = _ts(end)
        units.append(RawUnit(
            source_id=source_id,
            source_type="video",
            location=f"{start_str}-{end_str}",
            text=text,
            modality="transcript",
        ))

    for seg in video_content.segments:
        seg_len = _approx_tokens(seg.text)
        if buf_tokens + seg_len > chunk_size and seg_buffer:
            _flush(seg_buffer)
            seg_buffer = []
            buf_tokens = 0
        seg_buffer.append(seg)
        buf_tokens += seg_len

    _flush(seg_buffer)

    # Keyframe captions
    for kf in video_content.keyframes:
        ts = _ts(kf.timestamp)
        units.append(RawUnit(
            source_id=source_id,
            source_type="video",
            location=ts,
            text=f"[Video frame at {ts}] {kf.caption}",
            modality="image_caption",
        ))

    return units


def _ts(seconds: float) -> str:
    """Format seconds as m:ss."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"
