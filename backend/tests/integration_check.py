"""End-to-end API check intended for a running Docker Compose stack."""
import json
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000"
KEY = "integration-check-20261021"
BODY = {
    "source": "integration-demo",
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
assert status == 200 and health["database"] == "connected" and health["redis"] == "connected", health

status, _, job = request("/ingest", "POST", BODY, {"Idempotency-Key": KEY})
assert status == 202 and job["status"] in {"queued", "processing", "completed"}, job
job_id = job["id"]

status, replay_headers, replay = request("/ingest", "POST", BODY, {"Idempotency-Key": KEY})
assert status == 202 and replay["id"] == job_id
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
assert job["status"] == "completed", job

status, first_headers, records = request("/records?source=integration-demo&limit=10")
assert status == 200 and records["total"] == 2, records
status, second_headers, cached_records = request("/records?source=integration-demo&limit=10")
assert status == 200 and cached_records["total"] == 2
assert second_headers.get("x-cache") == "HIT", second_headers

print(json.dumps({"job_id": job_id, "records": records["total"], "cache": second_headers.get("x-cache")}))
sys.exit(0)
