# MVP Batch Processing Spec

This spec introduces simple batch processing to reduce UX latency, prevent full-job data loss, and avoid OOM issues on large lead files.

Design goal: **simple, robust, incremental**. No heavy orchestration.

---

## 1) Problems to solve (MVP scope)

Solve these now:

1. Long wait before any results become visible.
2. Full-job data loss if process crashes or external API fails mid-run.
3. Memory growth from holding all enriched leads in memory.

Do **not** solve now:

- distributed workers
- perfect idempotency across deploys
- dynamic auto-scaling
- full event streaming infra

---

## 2) Proposed approach (MVP)

Process input in fixed-size batches:

1. Parse full input once (mapped + validated rows).
2. Split into batches (`batch_size` from config).
3. For each batch:
   - run enrichment/verify/score synchronously for that subset
   - write batch leads immediately to DB
   - mark batch completed
   - update job progress counters
4. Job can be resumed from last completed batch.

Key behavior:

- **No global in-memory lead list**.
- **Results become visible after first batch**.
- **Crash impact limited to current batch**.

---

## 3) Minimal DB changes

Keep existing `jobs` and `leads`.

Add one new table:

```sql
CREATE TABLE IF NOT EXISTS job_batches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  batch_index INTEGER NOT NULL,
  start_row INTEGER NOT NULL,
  end_row INTEGER NOT NULL,
  status TEXT NOT NULL, -- pending|processing|completed|failed|terminated
  processed_rows INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  started_at TEXT,
  completed_at TEXT,
  UNIQUE(job_id, batch_index)
);
CREATE INDEX IF NOT EXISTS idx_job_batches_job_id ON job_batches(job_id);
```

Optional (recommended):

- Add `row_index INTEGER` to `leads` table, unique on `(job_id, row_index)` for dedupe safety on retries.

---

## 4) Job status model (simple)

Existing terminal states remain:

- `completed`
- `failed`
- `terminated`

Runtime states:

- `uploaded`
- `processing`

Batch statuses:

- `pending`
- `processing`
- `completed`
- `failed`
- `terminated`

Job-level rule:

- If all batches completed -> job `completed`
- If user terminated -> current+future batches `terminated`, job `terminated`
- If batch error -> job `failed` (always resumable via explicit resume action)

---

## 5) Config additions

Add to `sources.yaml`:

```yaml
sources:
  runtime:
    batch_size: 100
    stop_on_batch_error: true
```

Validation rules:

- `batch_size` integer, min 10, max 2000 (MVP guardrail)
- default to `100`

---

## 6) Backend flow changes

## 6.1 API job submit

- Keep existing `POST /jobs`.
- At submit time:
  - parse + map input once to determine total valid rows
  - create `job_batches` rows up front (`pending`)
  - kick worker

## 6.2 Worker execution loop

Pseudo flow:

1. Load active config/profile snapshot.
2. Read next `pending` batch for job.
3. Mark batch `processing`.
4. Run ingestion for rows in `[start_row:end_row]`.
5. Insert resulting leads immediately.
6. Mark batch `completed` and update job counts/progress.
7. Repeat until done or cancelled.

On error:

- mark current batch `failed` + error
- job `failed`
- retries are allowed by resuming the same job (no special retry policy logic required)

On terminate:

- stop before next batch or during stop checks
- mark current batch `terminated`
- job `terminated`

## 6.3 Ingestion entrypoint

Add a row-slice aware function:

- `ingest_rows_with_sources_config(rows, sources_cfg, should_stop)`

This avoids reparsing/re-reading input for every batch.

---

## 7) API additions (minimal)

Add one endpoint:

- `GET /jobs/{job_id}/batches`
  - returns batch list with statuses and errors

Add one control endpoint:

- `POST /jobs/{job_id}/resume`
  - allowed when job status is `failed` or `terminated`
  - sets job back to `processing`
  - converts resumable batches to `pending`:
    - `failed -> pending`
    - `terminated -> pending`
  - keeps `completed` batches unchanged

Enhance existing `GET /jobs/{job_id}` response:

- include progress:
  - `batches_total`
  - `batches_completed`
  - `rows_processed`
  - `rows_total`

No websocket required; dashboard keeps polling.

---

## 8) Dashboard behavior changes

Control Panel:

- show progress bar from `rows_processed / rows_total`
- show `completed_batches / total_batches`
- show `Resume` action when status is `failed` or `terminated`

Job History:

- show batch completion ratio and failed batch count

Data Explorer:

- already works with incremental DB inserts; just refresh polling while job processing

---

## 9) Failure handling (MVP)

Handle these explicitly:

- Crash/restart:
  - on startup, any `processing` batch -> reset to `pending` (safe replay)
  - worker resumes pending batches

- API quota exhausted:
  - store error on batch and job
  - keep completed batches available
  - operator can top up credits and use `resume`

- Duplicate writes on replay:
  - if `row_index` unique constraint exists, use upsert/ignore

---

## 10) What we intentionally defer

- per-batch retries/backoff policies
- cross-batch global dedupe improvements
- concurrent multi-batch execution
- server-side analytics materialization

---

## 11) Implementation checklist (small steps)

1. Add `runtime.batch_size` config + schema validation.
2. Add `job_batches` table + storage methods.
3. Add worker batch loop in `backend/api/jobs.py`.
4. Add row-slice ingestion function in `backend/core/ingestion.py`.
5. Add progress fields to `GET /jobs/{id}`.
6. Add `GET /jobs/{id}/batches`.
7. Add `POST /jobs/{id}/resume` for failed/terminated jobs.
8. Update dashboard polling to show batch progress + resume actions.
9. Add tests:
   - batch table lifecycle
   - partial progress persisted after forced failure
   - terminate during batch run
   - resume failed job continues from next pending batch

---

## 12) Success criteria

For a large input file:

- First results visible before full job completes.
- If process dies mid-run, already completed batches remain in DB.
- Resume works for both `failed` and `terminated` jobs.
- Resume continues from pending batches without reprocessing completed batches.
- Memory usage does not scale linearly with total rows.
