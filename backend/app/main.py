"""
FastAPI application factory.
Registers all routers, CORS, startup/shutdown hooks, and static file serving.
"""
from __future__ import annotations
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.routers import ingest, knowledge, chat, assessment, learner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Study Companion",
        description="Multimodal AI tutoring with source-grounded answers, adaptive assessment, and learner modelling.",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(ingest.router)
    app.include_router(knowledge.router)
    app.include_router(chat.router)
    app.include_router(assessment.router)
    app.include_router(learner.router)

    @app.on_event("startup")
    async def startup():
        logger.info("Initialising database...")
        await init_db()
        # Ensure upload dir exists
        Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
        Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
        logger.info("Startup complete.")

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "1.0.0"}

    # Serve uploaded files (for the in-app viewer)
    upload_path = Path(settings.upload_dir)
    if upload_path.exists():
        app.mount("/files", StaticFiles(directory=str(upload_path)), name="files")

    return app


app = create_app()
