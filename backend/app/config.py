"""
Application configuration loaded from .env
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    secret_key: str = "change-me"
    cors_origins: str = "http://localhost:3000"

    # LLM
    google_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "google"          # google | openai
    llm_model: str = "gemini-1.5-flash"
    vlm_model: str = "gemini-1.5-flash"   # same model handles images
    embedding_model: str = "models/text-embedding-004"

    # Database
    database_url: str = "sqlite+aiosqlite:///./studycompanion.db"

    # Vector store
    chroma_persist_dir: str = "./chroma_db"
    chroma_collection: str = "knowledge_units"

    # File storage
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 500

    # Whisper
    whisper_model: str = "small"
    whisper_device: str = "cpu"

    # Ingestion
    chunk_size_tokens: int = 400
    chunk_overlap_tokens: int = 50
    keyframe_interval_sec: int = 30

    # RAG
    retrieval_top_k: int = 20
    rerank_top_k: int = 5
    relevance_threshold: float = 0.35

    # BKT
    bkt_transit: float = 0.10
    bkt_slip_default: float = 0.10
    bkt_guess_default: float = 0.25
    bkt_prior_default: float = 0.30

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    use_celery: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
