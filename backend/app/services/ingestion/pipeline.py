"""
Ingestion pipeline orchestrator.
Coordinates: parse → chunk → embed → index → topic-extract → DB persist.
Runs as a background async task; streams progress updates via a shared queue.
"""
from __future__ import annotations
import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.source import Source
from app.models.knowledge import KnowledgeUnit, Topic, Prerequisite
from app.services.ingestion.chunker import (
    units_from_pdf_pages,
    units_from_pptx_slides,
    units_from_video,
    RawUnit,
)
from app.services.ingestion.topic_extractor import extract_topics, tag_units
from app.services.knowledge.vector_store import get_vector_store

logger = logging.getLogger(__name__)
settings = get_settings()

# Progress queues: source_id → asyncio.Queue of status strings
_progress_queues: dict[str, asyncio.Queue] = {}


def get_progress_queue(source_id: str) -> asyncio.Queue:
    if source_id not in _progress_queues:
        _progress_queues[source_id] = asyncio.Queue()
    return _progress_queues[source_id]


async def run_ingestion(source_id: str, file_path: Path | None = None, url: str | None = None) -> None:
    """
    Background task: ingest a source and persist all artifacts.
    Progress messages are put into the source's queue.
    """
    q = get_progress_queue(source_id)

    async def progress(msg: str):
        logger.info(f"[{source_id}] {msg}")
        await q.put({"status": "progress", "message": msg})

    async def fail(msg: str):
        logger.error(f"[{source_id}] FAILED: {msg}")
        await q.put({"status": "error", "message": msg})
        async with AsyncSessionLocal() as db:
            src = await db.get(Source, source_id)
            if src:
                src.status = "error"
                src.error_msg = msg
                await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            src = await db.get(Source, source_id)
            if not src:
                await fail("Source not found in DB")
                return
            src.status = "processing"
            await db.commit()

        await progress("Starting ingestion...")

        # ── Step 1: Parse ─────────────────────────────────────────────────────
        raw_units: list[RawUnit] = []

        if src.source_type == "pdf":
            await progress("Parsing PDF pages and figures...")
            from app.services.ingestion.pdf_parser import parse_pdf
            pages = await parse_pdf(Path(src.file_path))
            async with AsyncSessionLocal() as db:
                s = await db.get(Source, source_id)
                s.total_pages = len(pages)
                await db.commit()
            raw_units = units_from_pdf_pages(source_id, pages)
            await progress(f"Parsed {len(pages)} pages → {len(raw_units)} units")

        elif src.source_type == "pptx":
            await progress("Parsing PPTX slides and images...")
            from app.services.ingestion.pptx_parser import parse_pptx
            slides = await parse_pptx(Path(src.file_path))
            async with AsyncSessionLocal() as db:
                s = await db.get(Source, source_id)
                s.total_pages = len(slides)
                await db.commit()
            raw_units = units_from_pptx_slides(source_id, slides)
            await progress(f"Parsed {len(slides)} slides → {len(raw_units)} units")

        elif src.source_type == "video":
            await progress("Downloading/processing video (Whisper + keyframes)...")
            from app.services.ingestion.video import process_video, download_youtube
            video_path = file_path
            if url and not file_path:
                await progress("Downloading YouTube video...")
                upload_dir = Path(settings.upload_dir) / source_id
                upload_dir.mkdir(parents=True, exist_ok=True)
                video_path = await download_youtube(url, upload_dir)
                async with AsyncSessionLocal() as db:
                    s = await db.get(Source, source_id)
                    s.file_path = str(video_path)
                    await db.commit()
            vc = await process_video(video_path, keyframe_interval=settings.keyframe_interval_sec)
            async with AsyncSessionLocal() as db:
                s = await db.get(Source, source_id)
                s.duration_sec = vc.duration
                await db.commit()
            raw_units = units_from_video(source_id, vc)
            await progress(f"Transcribed {len(vc.segments)} segments, {len(vc.keyframes)} keyframes → {len(raw_units)} units")

        # ── Step 2: Topic extraction ─────────────────────────────────────────
        await progress("Extracting topic hierarchy...")
        all_texts = [u.text for u in raw_units]
        topic_graph = await extract_topics(all_texts, src.title)
        await progress(f"Extracted {len(topic_graph.nodes)} topics/concepts, {len(topic_graph.prerequisites)} prerequisites")

        # Persist topics
        async with AsyncSessionLocal() as db:
            for node in topic_graph.nodes.values():
                t = Topic(
                    id=node.id,
                    source_id=source_id,
                    student_id=src.student_id,
                    name=node.name,
                    description=node.description,
                    parent_id=node.parent_id,
                    level=node.level,
                )
                db.add(t)
            for from_id, to_id in topic_graph.prerequisites:
                p = Prerequisite(from_id=from_id, to_id=to_id)
                db.add(p)
            await db.commit()

        # ── Step 3: Tag units ─────────────────────────────────────────────────
        await progress("Tagging units with topics/concepts...")
        tags = await tag_units(all_texts, topic_graph)

        # ── Step 4: Embed and index in ChromaDB ───────────────────────────────
        await progress("Embedding and indexing knowledge units...")
        vs = get_vector_store()

        batch_size = 50
        db_units: list[KnowledgeUnit] = []
        chroma_batch: list[dict] = []

        for i, (unit, (topic_ids, concept_ids)) in enumerate(zip(raw_units, tags)):
            uid = str(uuid.uuid4())
            ku = KnowledgeUnit(
                unit_id=uid,
                source_id=source_id,
                source_type=unit.source_type,
                location=unit.location,
                text=unit.text,
                modality=unit.modality,
                topic_ids=topic_ids,
                concept_ids=concept_ids,
                embedding_id=uid,
            )
            db_units.append(ku)
            chroma_batch.append({
                "unit_id": uid,
                "text": unit.text,
                "metadata": {
                    "source_id": source_id,
                    "student_id": src.student_id,
                    "source_type": unit.source_type,
                    "location": unit.location,
                    "modality": unit.modality,
                    "topic_ids": topic_ids,
                    "concept_ids": concept_ids,
                },
            })

            if len(chroma_batch) >= batch_size:
                await vs.upsert_batch(chroma_batch)
                chroma_batch = []
                await progress(f"Indexed {i+1}/{len(raw_units)} units...")

        if chroma_batch:
            await vs.upsert_batch(chroma_batch)

        # Persist KnowledgeUnits to DB
        async with AsyncSessionLocal() as db:
            for ku in db_units:
                db.add(ku)
            await db.commit()

        # ── Step 5: Mark done ─────────────────────────────────────────────────
        async with AsyncSessionLocal() as db:
            s = await db.get(Source, source_id)
            s.status = "ready"
            await db.commit()

        await progress(f"✓ Ingestion complete: {len(db_units)} units indexed")
        await q.put({"status": "done", "message": "Ingestion complete", "unit_count": len(db_units)})

    except Exception as e:
        import traceback
        await fail(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
