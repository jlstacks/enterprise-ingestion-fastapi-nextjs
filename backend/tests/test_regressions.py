"""PR #1 regressions. Database tests require disposable ingestion_test services."""
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import pytest
from celery.exceptions import Reject, Retry
from fastapi.testclient import TestClient
from kombu.exceptions import OperationalError as PublishError
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import event, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import main, worker
from app.database import SessionLocal, engine
from app.models import Job, Record
from app.schemas import IngestRequest
from app.settings import settings

database = pytest.mark.skipif(os.getenv("RUN_DATABASE_TESTS") != "1", reason="requires disposable services")
client = TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture
def store():
    assert engine.url.database == "ingestion_test", "Never run destructive fixtures against application data"
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE ingested_records, ingestion_jobs RESTART IDENTITY CASCADE"))
    cache = Redis.from_url(settings.redis_url, decode_responses=True)
    assert cache.connection_pool.connection_kwargs["db"] == 15
    cache.flushdb()
    yield cache


def create_job(source="demo", value="old", key=None):
    body = {"source": source, "items": [{"external_id": "shared", "payload": {"value": value}}]}
    with patch.object(main.process_batch, "apply_async"):
        response = client.post("/ingest", json=body, headers={"Idempotency-Key": key or str(uuid4())})
    assert response.status_code == 202, response.text
    return response.json()["id"], body


@database
def test_duplicate_delivery_cannot_revert_a_newer_record(store, monkeypatch):
    old_id, _ = create_job()
    new_id, _ = create_job(value="new")
    original_inserting = threading.Event()
    release_original = threading.Event()
    duplicate_loaded = threading.Event()
    release_duplicate = threading.Event()
    real_get = Session.get

    def delayed_get(session, *args, **kwargs):
        job = real_get(session, *args, **kwargs)
        if threading.current_thread().name == "duplicate" and args[:2] == (Job, old_id):
            duplicate_loaded.set()
            assert release_duplicate.wait(10)
        return job

    def pause_original(connection, cursor, statement, parameters, context, executemany):
        if threading.current_thread().name == "original" and statement.startswith("INSERT INTO ingested_records"):
            original_inserting.set()
            assert release_original.wait(10)

    monkeypatch.setattr(Session, "get", delayed_get)
    event.listen(engine, "before_cursor_execute", pause_original)
    errors = []

    def execute(job_id):
        try:
            worker.process_batch.run(job_id)
        except Exception as exc:  # noqa: BLE001 - propagate thread failures to the main test
            errors.append(exc)

    original = threading.Thread(target=execute, args=(old_id,), name="original")
    duplicate = threading.Thread(target=execute, args=(old_id,), name="duplicate")
    try:
        original.start()
        assert original_inserting.wait(10)
        duplicate.start()
        # Vulnerable code reads stale processing state here. A fixed duplicate
        # blocks on the job lock and reads completed only after original commits.
        duplicate_loaded.wait(0.2)
        release_original.set()
        original.join(10)
        assert not original.is_alive() and not errors
        worker.process_batch.run(new_id)
        assert duplicate_loaded.wait(10)
        release_duplicate.set()
        duplicate.join(10)
        assert not duplicate.is_alive() and not errors
    finally:
        release_original.set()
        release_duplicate.set()
        original.join(10)
        if duplicate.ident:
            duplicate.join(10)
        event.remove(engine, "before_cursor_execute", pause_original)
    with SessionLocal() as session:
        record = session.scalar(select(Record).where(Record.source == "demo"))
        assert record.payload == {"value": "new"}
        assert record.job_id == new_id
        assert session.get(Job, old_id).attempts == 1


@database
def test_retry_exhaustion_keeps_recovery_scheduled_until_database_returns(store):
    job_id, _ = create_job()
    unavailable = OperationalError("SELECT", {}, Exception("database unavailable"))
    worker.process_batch.push_request(retries=3)
    try:
        with (
            patch.object(worker, "SessionLocal", side_effect=unavailable),
            patch.object(worker.process_batch, "retry", side_effect=Retry("recovery scheduled")),
            pytest.raises(Retry),
        ):
            worker.process_batch.run(job_id)
    finally:
        worker.process_batch.pop_request()
    worker.process_batch.push_request(retries=4)
    try:
        worker.process_batch.run(job_id)
    finally:
        worker.process_batch.pop_request()
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        assert job.status == "failed" and job.finished_at is not None
        assert "retries" in job.error
        assert not session.scalar(select(Record).where(Record.job_id == job_id))


@database
def test_ambiguous_publish_preserves_completed_work(store):
    def delivered_then_error(*, args, **kwargs):
        worker.process_batch.run(args[0])
        raise PublishError("lost reply after successful delivery")

    with patch.object(main.process_batch, "apply_async", side_effect=delivered_then_error):
        response = client.post("/ingest", json={"source": "demo", "items": [{"payload": {"ok": True}}]})
    with SessionLocal() as session:
        assert session.scalar(select(Job)).status == "completed"
        assert len(session.scalars(select(Record)).all()) == 1
    assert response.status_code == 200 and response.json()["status"] == "completed"


@database
def test_ambiguous_publish_preserves_processing_work(store):
    def claimed_then_error(*, args, **kwargs):
        with SessionLocal() as session:
            job = session.get(Job, args[0], with_for_update=True)
            job.status = "processing"
            session.commit()
        raise PublishError("lost reply after worker claimed delivery")

    with patch.object(main.process_batch, "apply_async", side_effect=claimed_then_error):
        response = client.post("/ingest", json={"source": "demo", "items": [{"payload": {"ok": True}}]})
    assert response.status_code == 202 and response.json()["status"] == "processing"


@database
@pytest.mark.parametrize("filtered_first", [False, True])
def test_cache_source_all_is_not_unfiltered(store, filtered_first):
    for source in ("all", "other"):
        job_id, _ = create_job(source)
        worker.process_batch.run(job_id)
    urls = ["/records?limit=12", "/records?source=all&limit=12"]
    for url in reversed(urls) if filtered_first else urls:
        response = client.get(url)
        assert response.status_code == 200
        assert response.json()["total"] == (1 if "source=" in url else 2)
    assert {item["source"] for item in client.get(urls[1]).json()["items"]} == {"all"}


@database
def test_failed_dispatch_replay_never_claims_acceptance(store):
    body = {"source": "demo", "items": [{"payload": {"ok": True}}]}
    key = str(uuid4())
    with patch.object(main, "redis_client") as cache:
        cache.return_value.ping.side_effect = RedisConnectionError("offline")
        first = client.post("/ingest", json=body, headers={"Idempotency-Key": key})
    assert first.status_code == 503
    with patch.object(main.process_batch, "apply_async") as publish:
        replay = client.post("/ingest", json=body, headers={"Idempotency-Key": key})
    assert replay.status_code == 503 and not publish.called


@database
def test_concurrent_same_key_creates_and_dispatches_one_job(store):
    key = str(uuid4())
    body = {"source": "demo", "items": [{"payload": {"ok": True}}]}
    with patch.object(main.process_batch, "apply_async") as publish, ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post("/ingest", json=body, headers={"Idempotency-Key": key}), range(4)))
    assert {r.status_code for r in results} == {202}
    assert len({r.json()["id"] for r in results}) == 1
    assert publish.call_count == 1


@database
def test_partial_batch_is_rolled_back_on_permanent_failure(store):
    job_id, _ = create_job()
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        job.payload = {**job.payload, "items": [*job.payload["items"],
                       {"external_id": "bad\u0000id", "payload": {"bad": True}}]}
        session.commit()
    worker.process_batch.run(job_id)
    with SessionLocal() as session:
        assert session.get(Job, job_id).status == "failed"
        assert not session.scalars(select(Record)).all()


@database
def test_recovery_keeps_original_delivery_if_retry_broker_fails(store):
    job_id, _ = create_job()
    unavailable = OperationalError("SELECT", {}, Exception("database unavailable"))
    worker.process_batch.push_request(retries=3)
    try:
        with (
            patch.object(worker, "SessionLocal", side_effect=unavailable),
            patch.object(worker.process_batch, "retry", side_effect=PublishError("broker unavailable")),
            pytest.raises(Reject) as rejection,
        ):
            worker.process_batch.run(job_id)
        assert rejection.value.requeue is True
    finally:
        worker.process_batch.pop_request()


def test_real_celery_retry_rejection_is_converted_to_requeue():
    task = worker.process_batch
    task.push_request(id=str(uuid4()), retries=3, called_directly=False, is_eager=False)
    try:
        with (
            patch.object(task, "signature_from_request") as signature,
            pytest.raises(Reject) as rejection,
        ):
            signature.return_value.apply_async.side_effect = PublishError("broker unavailable")
            worker.schedule_retry(task, "job-id", "terminal failure")
        assert rejection.value.requeue is True
    finally:
        task.pop_request()


def test_invalid_postgres_identifier_rejected_before_acceptance():
    response = client.post("/ingest", json={"source": "demo", "items": [{"external_id": "bad\u0000id", "payload": {"ok": True}}]})
    assert response.status_code == 422


@pytest.mark.parametrize("path,method", [("/ingest", "post"), ("/jobs", "get"), ("/jobs/missing", "get"), ("/records", "get"), ("/metrics", "get")])
def test_database_outage_is_structured_503(path, method):
    unavailable = OperationalError("SELECT with secret", {}, Exception("password=do-not-expose"))
    with patch.object(main, "SessionLocal", side_effect=unavailable), patch.object(main, "redis_client") as cache:
        cache.return_value.get.return_value = None
        kwargs = {"json": IngestRequest(source="demo", items=[{"payload": {"ok": True}}]).model_dump()} if method == "post" else {}
        response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 503
    assert response.json()["detail"] == "Database unavailable; retry later"
    assert "secret" not in response.text and "password" not in response.text
