import hashlib
import json
from typing import Any

from redis import Redis

from .models import Job, Record

RECORDS_VERSION_KEY = "ingestion:records:version"
METRICS_CACHE_KEY = "ingestion:metrics:v1"


def canonical_request_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def serialize_job(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "source": job.source,
        "status": job.status,
        "item_count": job.item_count,
        "attempts": job.attempts,
        "error": job.error,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


def serialize_record(record: Record) -> dict[str, Any]:
    return {
        "id": record.id,
        "job_id": record.job_id,
        "source": record.source,
        "external_id": record.external_id,
        "payload": record.payload,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def records_cache_key(cache: Redis, source: str | None, limit: int, offset: int) -> str:
    raw_version = cache.get(RECORDS_VERSION_KEY)
    version = raw_version.decode() if isinstance(raw_version, bytes) else (raw_version or "0")
    return f"ingestion:records:v{version}:{source or 'all'}:{limit}:{offset}"


def invalidate_read_caches(cache: Redis) -> None:
    cache.incr(RECORDS_VERSION_KEY)
    cache.delete(METRICS_CACHE_KEY)
