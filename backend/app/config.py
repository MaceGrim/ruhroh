"""Application configuration and settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ruhroh"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None
    qdrant_use_tls: bool = False
    qdrant_collection_name: str = "documents"

    # Supabase Auth
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # LLM Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    mistral_api_key: str = ""

    # RAG Configuration
    ruhroh_vector_weight: float = 0.6
    ruhroh_keyword_weight: float = 0.4
    ruhroh_rrf_k: int = 60
    ruhroh_enable_fallback: bool = False
    ruhroh_default_model: str = "gpt-4"
    ruhroh_embedding_model: str = "text-embedding-3-small"
    ruhroh_chunk_size: int = 512
    ruhroh_chunk_overlap: int = 50

    # Rate Limiting
    ruhroh_rate_limit_rpm: int = 60
    ruhroh_rate_limit_burst: int = 10

    # CORS
    cors_origins: str = "*"

    # File Storage
    upload_dir: str = "/app/uploads"
    processed_dir: str = "/app/processed"
    max_file_size: int = 500 * 1024 * 1024  # 500MB

    # Server
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @property
    def qdrant_url(self) -> str:
        """Build Qdrant URL from host and port."""
        protocol = "https" if self.qdrant_use_tls else "http"
        return f"{protocol}://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def rate_limit_rpm(self) -> int:
        """Rate limit requests per minute."""
        return self.ruhroh_rate_limit_rpm

    @property
    def rate_limit_burst(self) -> int:
        """Rate limit burst allowance."""
        return self.ruhroh_rate_limit_burst


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
