import logging
from datetime import UTC, datetime

from celery import Celery
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError

from .database import SessionLocal
from .models import Job, Record
from .services import invalidate_read_caches
from .settings import settings

logger = logging.getLogger(__name__)

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
)


def update_failure(job_id: str, message: str) -> None:
    try:
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            if job and job.status != "completed":
                job.status = "failed"
                job.error = message
                job.finished_at = datetime.now(UTC)
                session.commit()
    except Exception:
        logger.exception("Unable to persist failure state for job %s", job_id)


@celery.task(bind=True, name="ingestion.process_batch", max_retries=3)
def process_batch(self, job_id: str):
    """Persist one batch. Database uniqueness makes repeated task delivery safe."""
    try:
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            if not job or job.status == "completed":
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

        try:
            invalidate_read_caches(Redis.from_url(settings.redis_url, decode_responses=True))
        except RedisError:
            logger.warning("Job %s committed, but cache invalidation failed", job_id, exc_info=True)

        return {"job_id": job_id, "count": item_count}
    except (OperationalError, RedisError) as exc:
        logger.warning("Transient ingestion failure for job %s", job_id, exc_info=True)
        if self.request.retries >= self.max_retries:
            update_failure(job_id, "Processing failed after transient retries were exhausted")
            raise
        try:
            with SessionLocal() as session:
                job = session.get(Job, job_id)
                if job and job.status != "completed":
                    job.status = "queued"
                    job.error = "Transient dependency failure; retry scheduled"
                    session.commit()
        except Exception:
            logger.exception("Unable to persist retry state for job %s", job_id)
        raise self.retry(exc=exc, countdown=min(30, 2 ** (self.request.retries + 1)))
    except Exception:
        logger.exception("Permanent ingestion failure for job %s", job_id)
        update_failure(job_id, "Processing failed; inspect worker logs for details")
        raise
