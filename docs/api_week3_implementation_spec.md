# Week 3 — API endpoints (implementation spec)

Dashboard-first REST API over the existing enrichment pipeline, with **one shared ingestion core** used by both **CLI** (`runner.py run`) and **API** (FastAPI). **SQLite** remains the default job store; schema evolves to support dashboard listing, audit, and exports.

---

## 1. Goals

| Goal | Detail |
|------|--------|
| **Dashboard UX** | A Next.js (or other) UI can: upload or paste input, create a job, poll status, browse job history, inspect counts/errors, view and filter leads, download exports—without shell access. |
| **CLI parity** | Same enrichment behavior and config semantics as `python runner.py run ...` (same `sources.yaml` shape, same `ingest_to_structures*` entry point). |
| **Persistence** | Jobs, per-job leads, and enough **input provenance** to debug and re-export; optional retention policy later. |

---

## 2. Current baseline (do not regress)

Already in the repo:

- **FastAPI app**: `backend/api/routes.py` — `GET /health`, router under `/jobs`.
- **Jobs API** (`backend/api/jobs.py`):
  - `POST /jobs` — multipart: `file` + `input_format` (`csv` \| `json` \| `propflux`).
  - `GET /jobs/{job_id}` — status, counts, error.
  - `GET /jobs/{job_id}/results` — `202` while running, `500` on failed (with error), `200` + `leads` when completed.
- **SQLite** (`backend/core/storage_sqlite.py`): `jobs` + `leads` tables; `init_db`, `create_job`, `update_*`, `get_job`, `get_leads`, `insert_leads`.
- **Shared pipeline**: `ingest_to_structures` / `ingest_to_structures_with_sources_config` in `backend/core/ingestion.py` — API calls this; CLI `run_ingestion` wraps the same core and writes files.

This spec **extends** the above; it does not replace the ingestion algorithms.

---

## 3. Dashboard-centric design principles

1. **List + detail**: The UI needs **many jobs**, not only `GET` by id. Add **list** with sort (newest first) and pagination.
2. **Stable job identity**: Keep UUID `job_id`; expose **human labels** via optional `label` / `original_filename` from the client.
3. **Progress without giant payloads**: `GET /jobs/{id}` returns **summary** (status, counts, error, timestamps); full leads only via **results** or **export** endpoints.
4. **Two ways to submit input** (dashboard patterns):
   - **Multipart upload** (current) — file picker.
   - **JSON body** — paste PropFlux-style or `{ "leads": [...] }` without a file (same mapping as `load_json_mapped`).
5. **Exports** — `GET` with `Accept: text/csv` or `application/json`, or explicit `.../export?format=csv`, so the dashboard can offer “Download CSV / JSON”.
6. **Errors**: Failed jobs return **structured** error (`code`, `message`, optional `detail`) in JSON; HTTP status aligned with REST (e.g. `404` unknown job, `409` if results requested while failed—see below).

---

## 4. Data model

### 4.1 Job (logical)

| Field | Type | Notes |
|-------|------|--------|
| `job_id` | string (UUID) | Primary key |
| `status` | enum | `uploaded` → `processing` → `completed` \| `failed` (align naming with DB) |
| `input_format` | string | `csv` \| `json` \| `propflux` |
| `original_filename` | string \| null | From `Content-Disposition` or JSON body |
| `input_storage_path` | string \| null | Server path under `data/uploads/` (already derivable) |
| `input_sha256` | string \| null | Optional hash for dedup / integrity |
| `config_path` | string | Effective config used (default `config/sources.yaml`) |
| `created_at`, `started_at`, `completed_at` | ISO 8601 | Already partially present |
| `counts` | object \| null | From `summary["counts"]` |
| `rejected_rows` | array \| null | Stored JSON (already) |
| `error` | string \| null | User-safe message |

### 4.2 Lead (logical)

Unchanged: full canonical lead dict as JSON per row (same as CLI output rows), keyed by `job_id`.

### 4.3 SQLite migration (additive)

Extend `jobs` table (new columns with defaults so existing DBs upgrade safely):

- `original_filename TEXT`
- `input_sha256 TEXT` (optional)
- `label TEXT` (optional user-provided title for dashboard)

Add index: `CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);`

**Optional (Phase 1.5):** `job_inputs` table storing raw blob path + metadata only if you move away from single file per job (not required for MVP if `data/uploads/{job_id}.*` remains).

---

## 5. API surface (proposed)

Prefix: **`/api/v1`** recommended for future versioning; existing `/jobs` can remain as **aliases** during transition or be folded under v1 in one refactor.

### 5.1 Health

- `GET /health` — unchanged (load balancers).

### 5.2 Jobs — create

| Method | Path | Body | Response |
|--------|------|------|----------|
| `POST` | `/api/v1/jobs` | `multipart/form-data`: `file`, `input_format`, optional `label` | `{ "job_id", "status": "processing" }` |
| `POST` | `/api/v1/jobs` | `application/json`: `{ "input_format", "label?", "records" \| "leads" \| "data" }` — same list extraction rules as `load_json_mapped` | same as above |

Implementation: write JSON body to `data/uploads/{job_id}.json` when body is JSON; then same `_process_job` path.

### 5.3 Jobs — read

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/api/v1/jobs` | Paginated list: `{ "items": [...], "total": N, "limit": L, "offset": O }` |
| `GET` | `/api/v1/jobs/{job_id}` | Job metadata + counts + error; **no** full leads array |

Query params for list: `limit` (default 20, max 100), `offset`, optional `status` filter.

### 5.4 Results & exports (dashboard)

| Method | Path | Behavior |
|--------|------|----------|
| `GET` | `/api/v1/jobs/{job_id}/results` | If `completed`: `{ job_id, status, leads }`. If `processing`: `202` + `{ status }`. If `failed`: **`200`** or **`422`** with `{ status, error }` — **avoid raw `500`** for expected failure (improves dashboard handling). |
| `GET` | `/api/v1/jobs/{job_id}/export?format=json` | `Content-Disposition: attachment`; same rows as CLI `leads_*.json`. |
| `GET` | `/api/v1/jobs/{job_id}/export?format=csv` | CSV with `CANONICAL_FIELDS` header (match `run_ingestion`). |

Optional: `GET .../leads?min_score=70&limit=50&offset=0` for server-side filter (large tables).

---

## 6. Shared code path (CLI + API)

**Rule:** Both call **`ingest_to_structures_with_sources_config`** (or `ingest_to_structures` which loads YAML) — **no duplicated enrichment loops** in route handlers.

| Path | Entry |
|------|--------|
| CLI | `run_ingestion` → `ingest_to_structures_with_sources_config` → write JSON/CSV/summary |
| API | `_process_job` → `ingest_to_structures` → `insert_leads` + `update_job_completed` |

**Refactors to consider (small, high value):**

1. **`_process_job`** — accept `config_path: Path` (default `DEFAULT_CONFIG_PATH`) so tests and env override match CLI `--config`.
2. **Extract `run_pipeline_job(job_id, input_path, input_format, config_path) -> summary`** in `backend/core/ingestion.py` or `backend/core/job_runner.py` that returns `(leads, rejected, summary)` and is used by API; CLI `run_ingestion` calls the same then writes files. *Optional consolidation:* one function `execute_ingestion_job(...)` used by both.
3. **Environment** — `PROPINTEL_CONFIG` or `--config` for API process (document in README); dashboard deployments set the same env as CLI.

---

## 7. Configuration & secrets

- API server uses the **same** `config/sources.yaml` as CLI unless overridden.
- **Do not** return full YAML or API keys in JSON responses.
- For dashboard in production: restrict CORS to the frontend origin; keep API keys only on server (existing pattern for Serper / Google Maps).

---

## 8. Operational constraints

| Topic | Recommendation |
|-------|------------------|
| **Concurrency** | Keep `ThreadPoolExecutor` with bounded workers; document max concurrent jobs; optional queue later. |
| **Upload size** | Enforce `max_upload_mb` (Starlette/FastAPI limit) to protect disk. |
| **Idempotency** | `POST /jobs` creates a **new** job each time; no automatic dedup unless `input_sha256` + explicit policy added later. |
| **Cleanup** | Optional cron: delete uploads older than N days (document only for MVP). |

---

## 9. Testing

- **Unit**: Storage layer list/pagination; export CSV column order matches `CANONICAL_FIELDS`.
- **API**: `TestClient` for `POST` job (multipart + JSON body), poll until completed (mock ingestion or tiny fixture file), assert leads persisted.
- **Contract**: Snapshot OpenAPI (`/openapi.json`) for the dashboard team.

---

## 10. Out of scope (Week 3 spec)

- Authentication / multi-tenant users (add JWT or API keys in a later milestone).
- WebSockets / SSE for live progress (polling `GET /jobs/{id}` is enough for MVP).
- PostgreSQL (SQLite is sufficient until horizontal scale is required); migrate jobs/leads schema to PG using the same logical model when needed.

---

## 11. Definition of Done (Week 3 API checkbox)

- [ ] `GET /jobs` list + pagination backed by SQLite.
- [ ] `POST /jobs` accepts **file** and **JSON body** variants; both persist input and run the same pipeline as CLI.
- [ ] `GET /jobs/{id}/results` behavior documented: clear status for failed jobs (no ambiguous `500` for “job failed” if avoidable).
- [ ] Export endpoints return CSV/JSON aligned with CLI outputs.
- [ ] `ingest_to_structures*` remains the single enrichment implementation; any new glue is thin.
- [ ] README updated: API usage, env vars, dashboard CORS, example `curl` and upload.
- [ ] `PROJECT_NOTE.md` Week 3 “API endpoints” marked complete when the above ships.

---

## 12. File-level checklist (expected touches)

| Area | Files |
|------|--------|
| Routes | `backend/api/routes.py`, `backend/api/jobs.py` (split `dashboard.py` if desired) |
| Storage | `backend/core/storage_sqlite.py` — `list_jobs`, migration, new columns |
| Ingestion glue | `backend/core/ingestion.py` or new `backend/core/job_runner.py` |
| CLI | `runner.py` — optional `--config` passthrough parity with API env |
| Tests | `tests/test_api_jobs.py` (new), extend `tests/test_sqlite_storage.py` |
| Docs | `README.md` — API section; this spec stays the source for endpoint contracts |

---

*This spec is intentionally implementation-ready: database deltas, endpoint list, and shared-pipeline rule are actionable without locking frontend framework choices.*