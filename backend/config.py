"""
Centralized configuration for HelioOps backend.

All tuneable knobs in one place. Uses pydantic-settings so values
can be overridden via environment variables or a .env file.

Usage:
    from backend.config import settings
    print(settings.LOG_LEVEL)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="HELIOOPS_",
        extra="ignore",
    )

    PROJECT_ROOT: Path = Path(__file__).parent.parent

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    RELOAD: bool = True

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_MAX_TOKENS: int = 2048

    CHROMA_PERSIST_PATH: str = "data/chroma_db"

    ML_CHECKPOINT_DIR: str = "ML_after_CV/checkpoints"

    METRICS_ENABLED: bool = True
    METRICS_PATH: str = "/metrics"

    AVAILABLE_STORM_IDS: list[str] = ["2024-10-G4", "2024-05-G5"]

    @property
    def is_production(self) -> bool:
        return self.LOG_LEVEL.upper() in ("WARNING", "ERROR", "CRITICAL")


settings = Settings()