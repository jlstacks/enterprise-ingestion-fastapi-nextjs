from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngestItem(StrictModel):
    external_id: str | None = Field(default=None, min_length=1, max_length=128)
    payload: dict[str, Any] = Field(min_length=1)


class IngestRequest(StrictModel):
    source: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    items: list[IngestItem] = Field(min_length=1, max_length=100)

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        return value.strip().lower()


class JobResponse(BaseModel):
    id: str
    source: str
    status: Literal["queued", "processing", "completed", "failed"]
    item_count: int
    attempts: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RecordResponse(BaseModel):
    id: int
    job_id: str
    source: str
    external_id: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RecordPage(BaseModel):
    items: list[RecordResponse]
    total: int
    limit: int
    offset: int


class MetricsResponse(BaseModel):
    records: int
    jobs: int
    queued: int
    processing: int
    completed: int
    failed: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    api: Literal["online"] = "online"
    database: Literal["connected", "unavailable"]
    redis: Literal["connected", "unavailable"]
    worker: Literal["online", "offline", "unknown"]
