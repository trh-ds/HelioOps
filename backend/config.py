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
from backend.paths import CHECKPOINT_DIR, CHROMA_DIR
from pydantic import Field, field_validator
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

    # Gates CORS *and* the /ws/stream origin check -- an unlisted origin gets
    # WebSocket close code 4003, not a CORS error, so it looks like a backend
    # fault. Production origins are defaults rather than deploy-time-only
    # secrets so a forgotten HELIOOPS_CORS_ORIGINS cannot silently break the
    # browser client. Set that variable (JSON list) to override, e.g. to add a
    # Vercel preview origin, which has its own hostname.
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://localhost:5173",
        "https://helioops.dpdns.org",
        "https://heliops.dpdns.org",
        "https://frontend-olive-six-50.vercel.app",
    ]

    # The GROQ_* names are the LLM provider's, not ours, so they are read
    # without the HELIOOPS_ prefix. Without these aliases the env_prefix above
    # made Settings look for HELIOOPS_GROQ_API_KEY, so a correctly-configured
    # .env still left this empty and warned "GROQ_API_KEY not set" on every
    # boot — including in CI, which sets GROQ_API_KEY.
    # backend/genai/config.py reads os.getenv directly and was never affected,
    # which is why the LLM layer worked while this field stayed blank.
    GROQ_API_KEY: str = Field(default="", validation_alias="GROQ_API_KEY")
    # Kept in step with backend/genai/config.py, which is what the LLM layer
    # actually reads. llama-3.3-70b-versatile was decommissioned by Groq.
    GROQ_MODEL: str = Field(default="openai/gpt-oss-120b", validation_alias="GROQ_MODEL")
    GROQ_MAX_TOKENS: int = Field(default=1200, validation_alias="GROQ_MAX_TOKENS")

    CHROMA_PERSIST_PATH: str = str(CHROMA_DIR)

    ML_CHECKPOINT_DIR: str = str(CHECKPOINT_DIR)

    RESULT_REPOSITORY: str = "memory"
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_PIPELINE_RESULTS_TABLE: str = "pipeline_runs"
    SUPABASE_ADVISORIES_TABLE: str = "advisories"
    SUPABASE_VERIFIED_ADVISORIES_TABLE: str = "verified_advisories"
    SUPABASE_PROVENANCE_TRACES_TABLE: str = "provenance_traces"

    METRICS_ENABLED: bool = True
    METRICS_PATH: str = "/metrics"

    AVAILABLE_STORM_IDS: list[str] = ["2024-10-G4", "2024-05-G5"]

    @field_validator("GROQ_API_KEY")
    @classmethod
    def validate_groq_key(cls, v: str) -> str:
        if not v:
            import warnings

            warnings.warn("GROQ_API_KEY not set — GenAI advisories will fail")
        return v

    @property
    def is_production(self) -> bool:
        return self.LOG_LEVEL.upper() in ("WARNING", "ERROR", "CRITICAL")


settings = Settings()
