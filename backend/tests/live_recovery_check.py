"""Exercise real retry exhaustion using CI's worker with an unavailable database."""
import json
import sys
from uuid import uuid4

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Job
from app.worker import celery, process_batch

KEY = "ci-recovery-check"
if sys.argv[1] == "queue":
    with SessionLocal() as session:
        job = Job(id=str(uuid4()), idempotency_key=f"{KEY}-{uuid4()}", request_hash="0" * 64,
                  source=KEY, payload={"source": KEY, "items": [{"payload": {"test": True}}]},
                  item_count=1, status="queued")
        session.add(job)
        session.commit()
        process_batch.apply_async(args=[job.id], task_id=job.id)
        print(json.dumps({"recovery_job": job.id}))
else:
    import time
    for _ in range(40):
        with SessionLocal() as session:
            job = session.scalar(select(Job).where(Job.source == KEY).order_by(Job.created_at.desc()))
            if sys.argv[1] == "await-retry":
                metadata = celery.AsyncResult(job.id)._get_task_meta()
                if metadata.get("status") == "RETRY" and metadata.get("retries", 0) >= 3:
                    assert job.status == "queued" and job.finished_at is None
                    print(json.dumps({"status": "recovery scheduled", "retries": metadata["retries"]}))
                    break
            elif job.status == "failed":
                assert job.finished_at and "retries" in job.error
                print(json.dumps({"recovery_job": job.id, "status": job.status}))
                break
        time.sleep(1)
    else:
        raise AssertionError("Recovery delivery did not persist terminal state")
