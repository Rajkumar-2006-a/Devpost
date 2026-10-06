"""
Ingestion router.
Handles file uploads and YouTube URL ingestion.
Streams progress via SSE.
"""
from __future__ import annotations
import asyncio
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.source import Source
from app.services.ingestion.pipeline import run_ingestion, get_progress_queue
import json

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])
settings = get_settings()


@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    student_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF or PPTX file for ingestion."""
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in (".pdf", ".pptx", ".ppt", ".mp4", ".mov", ".avi"):
        raise HTTPException(400, f"Unsupported file type: {ext}")

    source_type = "pdf" if ext == ".pdf" else ("pptx" if ext in (".pptx", ".ppt") else "video")

    # Save file
    source_id = str(uuid.uuid4())
    upload_dir = Path(settings.upload_dir) / source_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename

    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File too large")

    with open(file_path, "wb") as f:
        f.write(content)

    # Create source record
    src = Source(
        id=source_id,
        student_id=student_id,
        source_type=source_type,
        title=Path(filename).stem,
        file_path=str(file_path),
        status="pending",
    )
    db.add(src)
    await db.commit()

    # Launch ingestion in background
    background_tasks.add_task(run_ingestion, source_id, file_path)

    return {"source_id": source_id, "status": "pending", "title": src.title}


@router.post("/youtube")
async def ingest_youtube(
    background_tasks: BackgroundTasks,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a YouTube video by URL."""
    url = body.get("url", "").strip()
    student_id = body.get("student_id", "").strip()
    if not url or not student_id:
        raise HTTPException(400, "url and student_id are required")

    source_id = str(uuid.uuid4())
    src = Source(
        id=source_id,
        student_id=student_id,
        source_type="video",
        title=url,
        url=url,
        status="pending",
    )
    db.add(src)
    await db.commit()

    background_tasks.add_task(run_ingestion, source_id, None, url)

    return {"source_id": source_id, "status": "pending"}


@router.get("/status/{source_id}")
async def stream_status(source_id: str):
    """SSE endpoint streaming ingestion progress."""
    q = get_progress_queue(source_id)

    async def event_generator():
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=30)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("status") in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield "data: {\"status\": \"heartbeat\"}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/sources")
async def list_sources(student_id: str, db: AsyncSession = Depends(get_db)):
    """List all sources for a student."""
    result = await db.execute(
        select(Source).where(Source.student_id == student_id).order_by(Source.created_at.desc())
    )
    sources = result.scalars().all()
    return [
        {
            "id": s.id,
            "title": s.title,
            "source_type": s.source_type,
            "status": s.status,
            "total_pages": s.total_pages,
            "duration_sec": s.duration_sec,
            "error_msg": s.error_msg,
            "created_at": s.created_at.isoformat(),
        }
        for s in sources
    ]


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a source and all its knowledge units."""
    from app.services.knowledge.vector_store import get_vector_store
    vs = get_vector_store()
    vs.delete_by_source(source_id)

    src = await db.get(Source, source_id)
    if src:
        await db.delete(src)
        await db.commit()
    return {"deleted": source_id}
