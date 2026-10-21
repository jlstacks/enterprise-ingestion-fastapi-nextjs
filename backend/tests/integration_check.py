"""End-to-end API check intended for a running Docker Compose stack."""
import json
import os
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

BASE_URL = os.getenv("TEST_API_URL", "http://127.0.0.1:8000")
KEY = f"integration-{uuid4()}"
BODY = {
    "source": KEY,
    "items": [
        {"external_id": "demo-001", "payload": {"account": "Northstar", "stage": "qualified"}},
        {"external_id": "demo-002", "payload": {"account": "Evergreen", "stage": "review"}},
    ],
}


def request(path: str, method: str = "GET", body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(
        f"{BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urlopen(req, timeout=10) as response:
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return response.status, response_headers, json.load(response)
    except HTTPError as exc:
        response_headers = {key.lower(): value for key, value in exc.headers.items()}
        return exc.code, response_headers, json.load(exc)


status, _, health = request("/health")
assert status == 200 and health["status"] == "ok" and health["worker"] == "online", health

status, _, job = request("/ingest", "POST", BODY, {"Idempotency-Key": KEY})
assert status == 202 and job["status"] in {"queued", "processing", "completed"}, job
job_id = job["id"]

status, replay_headers, replay = request("/ingest", "POST", BODY, {"Idempotency-Key": KEY})
assert status in {200, 202} and replay["id"] == job_id
assert replay_headers.get("idempotency-replayed") == "true"

conflict = {**BODY, "items": [{"external_id": "demo-003", "payload": {"different": True}}]}
status, _, _ = request("/ingest", "POST", conflict, {"Idempotency-Key": KEY})
assert status == 409

status, _, _ = request("/ingest", "POST", {"source": "bad", "items": []})
assert status == 422

for _ in range(30):
    status, _, job = request(f"/jobs/{job_id}")
    assert status == 200
    if job["status"] in {"completed", "failed"}:
        break
    time.sleep(1)
assert job["status"] == "completed" and job["attempts"] >= 1 and job["finished_at"], job

status, first_headers, records = request(f"/records?source={KEY}&limit=10")
assert status == 200 and records["total"] == 2, records
assert {item["job_id"] for item in records["items"]} == {job_id}
assert {item["external_id"]: item["payload"] for item in records["items"]} == {
    item["external_id"]: item["payload"] for item in BODY["items"]
}
status, second_headers, cached_records = request(f"/records?source={KEY}&limit=10")
assert status == 200 and cached_records["total"] == 2
assert second_headers.get("x-cache") == "HIT", second_headers

# Re-submit as a different job to exercise retry-safe record upserts and cache invalidation.
status, _, second_job = request("/ingest", "POST", BODY, {"Idempotency-Key": f"{KEY}-upsert"})
assert status == 202 and second_job["id"] != job_id
for _ in range(30):
    _, _, updated_job = request(f"/jobs/{second_job['id']}")
    if updated_job["status"] in {"completed", "failed"}:
        break
    time.sleep(1)
assert updated_job["status"] == "completed", updated_job
_, _, updated = request(f"/records?source={KEY}&limit=10")
assert updated["total"] == 2
assert {item["job_id"] for item in updated["items"]} == {second_job["id"]}

print(json.dumps({"job_id": job_id, "records": records["total"], "cache": second_headers.get("x-cache")}))
sys.exit(0)
