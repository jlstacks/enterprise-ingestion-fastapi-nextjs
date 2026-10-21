import json
from uuid import uuid4

from celery.exceptions import CeleryError
from fastapi import FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from kombu.exceptions import OperationalError as KombuOperationalError
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .database import SessionLocal, engine
from .models import Job, Record
from .schemas import (
    HealthResponse,
    IngestRequest,
    JobResponse,
    MetricsResponse,
    RecordPage,
)
from .services import (
    METRICS_CACHE_KEY,
    canonical_request_hash,
    records_cache_key,
    serialize_job,
    serialize_record,
)
from .settings import settings
from .worker import celery, process_batch

app = FastAPI(
    title="Enterprise Ingestion API",
    description="Asynchronous ingestion, operational status, and cache-backed record retrieval.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)


def redis_client() -> Redis:
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def worker_status() -> str:
    try:
        replies = celery.control.inspect(timeout=settings.worker_health_timeout_seconds).ping()
        return "online" if replies else "offline"
    except (CeleryError, KombuOperationalError, RedisError, OSError):
        return "unknown"


def mark_dispatch_failed(job_id: str) -> None:
    with SessionLocal() as session:
        failed = session.get(Job, job_id)
        if failed:
            failed.status = "failed"
            failed.error = "Message broker unavailable; job was not dispatched"
            session.commit()


@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> JSONResponse | dict:
    database = "connected"
    redis = "connected"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database = "unavailable"
    try:
        redis_client().ping()
    except RedisError:
        redis = "unavailable"

    worker = worker_status() if redis == "connected" else "unknown"
    if database == "unavailable" or redis == "unavailable":
        payload = {
            "status": "unavailable",
            "api": "online",
            "database": database,
            "redis": redis,
            "worker": worker,
        }
        return JSONResponse(status_code=503, content=payload)
    return {
        "status": "ok" if worker == "online" else "degraded",
        "api": "online",
        "database": database,
        "redis": redis,
        "worker": worker,
    }


@app.post("/ingest", status_code=202, response_model=JobResponse, tags=["ingestion"])
def ingest(
    request: IngestRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if idempotency_key is not None and not (1 <= len(idempotency_key) <= 128):
        raise HTTPException(status_code=422, detail="Idempotency-Key must be 1-128 characters")

    payload = request.model_dump(mode="json")
    request_hash = canonical_request_hash(payload)
    key = idempotency_key or str(uuid4())

    with SessionLocal() as session:
        existing = session.scalar(select(Job).where(Job.idempotency_key == key))
        if existing:
            if existing.request_hash != request_hash:
                raise HTTPException(status_code=409, detail="Idempotency key reused with different data")
            response.headers["Idempotency-Replayed"] = "true"
            return serialize_job(existing)

        job = Job(
            id=str(uuid4()),
            idempotency_key=key,
            request_hash=request_hash,
            source=request.source,
            payload=payload,
            item_count=len(request.items),
            status="queued",
        )
        session.add(job)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.scalar(select(Job).where(Job.idempotency_key == key))
            if existing and existing.request_hash == request_hash:
                response.headers["Idempotency-Replayed"] = "true"
                return serialize_job(existing)
            raise HTTPException(status_code=409, detail="Idempotency key already used")
        session.refresh(job)
        result = serialize_job(job)

    try:
        # Fail quickly before entering Celery's transport connection path. The
        # publish exception handler below still protects against a race where
        # Redis becomes unavailable after this preflight succeeds.
        redis_client().ping()
        process_batch.apply_async(args=[job.id], task_id=job.id, retry=False)
    except (CeleryError, KombuOperationalError, RedisError, OSError):
        mark_dispatch_failed(result["id"])
        raise HTTPException(status_code=503, detail="Message broker unavailable; job marked failed")

    try:
        redis_client().delete(METRICS_CACHE_KEY)
    except RedisError:
        pass
    return result


@app.get("/jobs", response_model=list[JobResponse], tags=["operations"])
def jobs(limit: int = Query(10, ge=1, le=100)):
    with SessionLocal() as session:
        values = session.scalars(select(Job).order_by(Job.created_at.desc()).limit(limit)).all()
        return [serialize_job(value) for value in values]


@app.get("/jobs/{job_id}", response_model=JobResponse, tags=["operations"])
def job_status(job_id: str):
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return serialize_job(job)


@app.get("/metrics", response_model=MetricsResponse, tags=["operations"])
def metrics(response: Response):
    cache = None
    try:
        cache = redis_client()
        cached = cache.get(METRICS_CACHE_KEY)
        if cached:
            response.headers["X-Cache"] = "HIT"
            return json.loads(cached)
    except RedisError:
        cache = None

    with SessionLocal() as session:
        records_count = session.scalar(select(func.count()).select_from(Record)) or 0
        jobs_total = session.scalar(select(func.count()).select_from(Job)) or 0
        statuses = session.execute(select(Job.status, func.count()).group_by(Job.status)).all()
    counts = {status: count for status, count in statuses}
    payload = {
        "records": records_count,
        "jobs": jobs_total,
        "queued": counts.get("queued", 0),
        "processing": counts.get("processing", 0),
        "completed": counts.get("completed", 0),
        "failed": counts.get("failed", 0),
    }
    if cache:
        try:
            cache.setex(METRICS_CACHE_KEY, settings.cache_ttl_seconds, json.dumps(payload))
        except RedisError:
            pass
    response.headers["X-Cache"] = "MISS"
    return payload


@app.get("/records", response_model=RecordPage, tags=["records"])
def records(
    response: Response,
    limit: int = Query(12, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10_000),
    source: str | None = Query(default=None, min_length=1, max_length=80),
):
    normalized_source = source.strip().lower() if source else None
    cache = None
    key = None
    try:
        cache = redis_client()
        key = records_cache_key(cache, normalized_source, limit, offset)
        cached = cache.get(key)
        if cached:
            response.headers["X-Cache"] = "HIT"
            return json.loads(cached)
    except RedisError:
        cache = None

    with SessionLocal() as session:
        predicate = Record.source == normalized_source if normalized_source else None
        count_statement = select(func.count()).select_from(Record)
        rows_statement = select(Record).order_by(Record.created_at.desc()).limit(limit).offset(offset)
        if predicate is not None:
            count_statement = count_statement.where(predicate)
            rows_statement = rows_statement.where(predicate)
        total = session.scalar(count_statement) or 0
        rows = session.scalars(rows_statement).all()
        payload = {
            "items": [serialize_record(record) for record in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    if cache and key:
        try:
            cache.setex(key, settings.cache_ttl_seconds, json.dumps(payload))
        except RedisError:
            pass
    response.headers["X-Cache"] = "MISS"
    return payload
