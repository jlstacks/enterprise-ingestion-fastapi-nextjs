import logging
from contextlib import contextmanager
from datetime import UTC, datetime

from celery import Celery
from celery.exceptions import Reject
from kombu.exceptions import OperationalError as PublishError
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from .database import SessionLocal, engine
from .models import Job, Record
from .services import invalidate_read_caches
from .settings import settings

logger = logging.getLogger(__name__)
PROCESSING_RETRIES = 3
EXHAUSTED = "Processing failed after transient retries were exhausted"

celery = Celery("ingestion", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_publish_retry=False,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=2,
    broker_transport_options={
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
        "retry_on_timeout": False,
    },
    result_expires=3600,
    result_extended=True,
    redis_socket_connect_timeout=2,
    redis_socket_timeout=2,
    result_backend_always_retry=False,
)


@contextmanager
def locked_session(job_id: str):
    """Hold a per-job PostgreSQL session lock across status/data commits.

    Pin the connection: a Session alone may return it to the pool at commit.
    Process death releases the lock so late delivery can safely resume work.
    """
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(hashtextextended(:id, 0))"), {"id": job_id})
        connection.commit()
        try:
            with SessionLocal(bind=connection) as session:
                yield session
        finally:
            try:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(hashtextextended(:id, 0))"), {"id": job_id})
                connection.commit()
            except SQLAlchemyError:
                # Never return a connection with an unknown session lock to the pool.
                connection.invalidate()


def update_failure(job_id: str, message: str) -> dict:
    with locked_session(job_id) as session:
        job = session.get(Job, job_id, with_for_update=True, populate_existing=True)
        if not job or job.status in {"completed", "failed"}:
            return {"job_id": job_id, "skipped": True}
        job.status = "failed"
        job.error = message
        job.finished_at = datetime.now(UTC)
        session.commit()
    return {"job_id": job_id, "status": "failed"}


def schedule_retry(task, job_id: str, failure_reason: str | None = None):
    try:
        raise task.retry(
            args=[job_id], kwargs={"failure_reason": failure_reason},
            countdown=min(30, 2 ** min(task.request.retries + 1, 5)),
            max_retries=None,
        )
    except (Reject, PublishError, RedisError, OSError) as exc:
        # Keep the original delivery unacknowledged if publishing its retry fails.
        raise Reject("Retry broker unavailable", requeue=True) from exc


def finish_failure(task, job_id: str, message: str):
    try:
        result = update_failure(job_id, message)
    except OperationalError:
        logger.warning("Deferring terminal-state persistence for job %s", job_id)
        return schedule_retry(task, job_id, message)
    invalidate_caches(job_id)
    return result


def invalidate_caches(job_id: str):
    try:
        cache = Redis.from_url(settings.redis_url, decode_responses=True,
                               socket_connect_timeout=2, socket_timeout=2)
        invalidate_read_caches(cache)
    except RedisError:
        logger.warning("Job %s committed; read caches may remain stale until TTL", job_id)


@celery.task(bind=True, name="ingestion.process_batch", max_retries=None)
def process_batch(self, job_id: str, failure_reason: str | None = None):
    """Bound processing retries, but retain recovery work until status is durable."""
    if failure_reason or self.request.retries > PROCESSING_RETRIES:
        return finish_failure(self, job_id, failure_reason or EXHAUSTED)
    try:
        with locked_session(job_id) as session:
            job = session.get(Job, job_id, with_for_update=True, populate_existing=True)
            if not job or job.status in {"completed", "failed"}:
                return {"job_id": job_id, "skipped": True}

            job.status = "processing"
            job.attempts += 1
            job.started_at = job.started_at or datetime.now(UTC)
            job.error = None
            session.commit()

            for index, item in enumerate(job.payload["items"]):
                external_id = item.get("external_id") or f"{job_id}:{index}"
                stmt = insert(Record).values(
                    job_id=job.id,
                    source=job.source,
                    external_id=external_id,
                    payload=item["payload"],
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_source_external_id",
                    set_={
                        "payload": item["payload"],
                        "job_id": job.id,
                        "updated_at": datetime.now(UTC),
                    },
                )
                session.execute(stmt)
            job.status = "completed"
            job.error = None
            job.finished_at = datetime.now(UTC)
            item_count = job.item_count
            session.commit()

        invalidate_caches(job_id)

        return {"job_id": job_id, "count": item_count}
    except OperationalError:
        logger.warning("Transient ingestion failure for job %s", job_id, exc_info=True)
        if self.request.retries >= PROCESSING_RETRIES:
            return finish_failure(self, job_id, EXHAUSTED)
        return schedule_retry(self, job_id)
    except Exception:
        logger.exception("Permanent ingestion failure for job %s", job_id)
        return finish_failure(self, job_id, "Processing failed; inspect worker logs for details")
