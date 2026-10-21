# PR #1 remediation evidence

The independent review covered original commit `c96d8b8`. This follow-up preserves
the application architecture and addresses its three P1 and seven P2 findings.
No dashboard redesign or portfolio change is included.

## Finding-to-resolution map

| Finding | Correction | Regression evidence |
|---|---|---|
| P1-1 concurrent duplicate delivery | A connection-pinned PostgreSQL session advisory lock spans the status/data commits. Job state is reloaded with a row lock; completed/failed deliveries skip work. | `test_duplicate_delivery_cannot_revert_a_newer_record` pauses original and duplicate deliveries around the exact stale-read interleaving; a newer job's payload and owner remain intact. |
| P1-2 terminal failure persistence | Processing retries are bounded independently of terminal bookkeeping. Recovery deliveries keep retrying until failure is durable; a failed retry publish requeues the original delivery, including Celery's wrapped Reject exception. | `test_retry_exhaustion_keeps_recovery_scheduled_until_database_returns`, `test_recovery_keeps_original_delivery_if_retry_broker_fails`, `test_real_celery_retry_rejection_is_converted_to_requeue`, plus actual Celery exhaustion/recovery in CI. |
| P1-3 ambiguous publishing | Dispatch cancellation atomically updates only queued jobs. Processing/completed states cannot regress; uncertain dispatch is described honestly. | `test_ambiguous_publish_preserves_completed_work` and `test_ambiguous_publish_preserves_processing_work`. |
| P2-1 cache collision | The query portion encodes `[source, limit, offset]` as JSON, distinguishing null from the valid literal source `all`. | `test_cache_source_all_is_not_unfiltered` tests both cache-warming orders against PostgreSQL/Redis. |
| P2-2 failed replay | Failed jobs replay with HTTP 503; completed jobs return 200; outstanding jobs return 202. Conflicting requests remain 409. | `test_failed_dispatch_replay_never_claims_acceptance`, `test_concurrent_same_key_creates_and_dispatches_one_job`, and the fresh integration script. |
| P2-3 stale green health | Health is refreshed independently, preserves the structured dependency body on HTTP 503, clears on transport failure, and labels retained data stale. A request generation prevents older results replacing newer filter state. | Five `frontend/tests/operations.test.mjs` regressions cover dependency 503, transport failure, worker offline, independent health updates, and invalid upstream responses. |
| P2-4 integration false positives | Each run generates a new source/key and verifies actual worker attempts, content, record ownership, upserts, and invalidation. CI includes real services and a worker-stopped negative check. | The same integration script passes with a worker and exits nonzero after that worker stops. `live_recovery_check.py` verifies actual retry exhaustion and recovery, then persistence across restart. |
| P2-5 advisory coverage | Patched pip/pytest; audit all npm and installed Python dependencies with exact reviewed exceptions. Unknown advisories fail CI. | `test_security_audit.py` rejects new advisories and changed affected versions; full audits report only documented exceptions in `SECURITY.md`; `pip check` passes. |
| P2-6 invalid identifiers | Pydantic rejects control characters, NUL, and invalid Unicode surrogates in external IDs before database work. | `test_invalid_postgres_identifier_rejected_before_acceptance` requires HTTP 422. |
| P2-7 database error contract | Transient database/pool availability errors are translated into sanitized JSON HTTP 503 responses. | Five parameterized `test_database_outage_is_structured_503` cases cover ingestion, jobs, job status, records, and metrics without exposing injected secret text. |

`test_partial_batch_is_rolled_back_on_permanent_failure` additionally verifies
that one bad record does not leave a partially committed batch.

## Validation

- Before fixes, the initial backend regressions reproduced 12 failures against
  the original implementation; the concurrent same-key positive control passed.
- After fixes: **28 backend tests passed** with disposable PostgreSQL 16 and
  Redis 7.2. Database fixtures enforce database `ingestion_test` and Redis index
  15 before truncating/flushing synthetic data.
- **Five frontend tests passed**, as did ESLint, TypeScript, and the Next.js
  production build inside the Node 22 Docker build.
- Ruff and `pip check` passed.
- Full npm/Python audits reported no unreviewed advisories; the npm production
  audit has zero reported advisories. Reviewed build-tool/Starlette exceptions
  remain visible and documented rather than hidden by a production-only audit.
- The API, worker, frontend, backend test images, Redis and PostgreSQL stack built
  and started independently of existing local projects. Frontend, API proxy, and
  OpenAPI docs returned healthy responses.
- Fresh ingestion completed through the real worker. Content, idempotency,
  conflicts, invalid requests, cache hits, upserts and invalidation passed.
- The integration script failed as intended with the isolated worker stopped.
- Stopping the isolated Redis service produced HTTP 503 with a durable cancelled
  job; replay after Redis recovery remained 503. Stopping isolated PostgreSQL
  produced the sanitized JSON `Database unavailable; retry later` with HTTP 503.
- A worker with an unavailable database exhausted three processing retries and
  retained a recovery delivery. After graceful handoff to a normal worker, the
  job became durably failed. That state survived a full stack restart, and a
  subsequent fresh ingestion completed.

GitHub Actions independently repeats frontend, backend, security, Compose, and
real-stack integration validation on the remediation commit. Its check status
is the source of truth for the published revision.

## Remaining boundaries

- Terminal recovery depends on retained Redis messages and eventual worker and
  database availability. Forced worker loss can defer redelivery to the default
  one-hour Redis visibility timeout; the recovery CI scenario uses graceful
  handoff so it tests PostgreSQL recovery independently of forced-loss timing.
- No transaction spans PostgreSQL job creation and Redis publish. The documented
  process-crash gap still requires an outbox/reconciliation mechanism before any
  stronger delivery claim.
- Separate jobs follow commit order, not source event-time ordering.
- Cache invalidation is best effort; record/metrics TTL bounds normal stale cache
  retention. No zero-staleness guarantee is made.
- Exact reviewed dependency exceptions remain; see `SECURITY.md` for versions,
  advisory IDs, applicability, and reevaluation triggers.
- Authentication, TLS ingress, request-size/rate limits, managed secrets/backups,
  tenant isolation and production observability remain future hardening work.
