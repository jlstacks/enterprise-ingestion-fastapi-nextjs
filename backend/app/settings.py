from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    environment: str = "local"
    database_url: str = "postgresql://ingestion:ingestion@db:5432/ingestion"
    redis_url: str = "redis://cache:6379/0"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cache_ttl_seconds: int = Field(default=20, ge=1, le=3600)
    worker_health_timeout_seconds: float = Field(default=0.5, ge=0.1, le=5)

    @property
    def sqlalchemy_database_url(self) -> str:
        return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
