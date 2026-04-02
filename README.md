# PropIntel

Production-style real estate lead intelligence platform.

## Initial Structure

- `backend/api` - FastAPI route handlers and job endpoints
- `backend/services` - enrichment, scraping, verification, scoring logic
- `backend/core` - parsing, normalization, deduplication utilities
- `frontend/dashboard` - dashboard app scaffold (Next.js planned)
- `config/sources.yaml` - configurable source extraction settings
- `output` - generated export artifacts
- `logs` - runtime logs written by the CLI (timestamped files under `logs/`)
- `runner.py` - CLI entrypoint for API and pipeline runs

## Quick Start

1. Create a Python 3.11+ virtual environment
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Start the API via CLI:
   - `python runner.py api --reload`
4. Health check:
   - `curl http://127.0.0.1:8000/health`

## CLI Usage

`runner.py` supports two subcommands:

- `api` - start the FastAPI server
- `run` - execute the local pipeline scaffold with CLI configuration

Examples:

- Start API with custom host/port:
  - `python runner.py api --host 0.0.0.0 --port 8080 --reload --log-level debug`
- Run pipeline with CSV input:
  - `python runner.py run --input data/leads.csv --input-format csv --config config/sources.yaml --output output --log-level info`
- Run pipeline with PropFlux input:
  - `python runner.py run --input data/propflux_export.json --input-format propflux`

All CLI runs log to `logs/propintel_YYYYMMDD_HHMMSS.log` and stderr via `loguru`.

### Pipeline Outputs (CLI `run`)
The CLI creates a timestamped folder under `--output` (defaults to `output/`), like:
`output/20260325_153000/`

Inside that folder, filenames include the same timestamp:
- `leads_<timestamp>.json`
- `leads_<timestamp>.csv`
- `rejected_rows_<timestamp>.json`
- `run_summary_<timestamp>.json`

### Basic Website Enrichment
- Website enrichment runs during pipeline processing (best effort, non-fatal).
- If a lead has no `website`, the pipeline can attempt discovery via Serper using `company_name` (+ optional `location`).
- If no website is found, enrichment is skipped for that lead.
- Configure behavior in `config/sources.yaml` under `sources.website` (`enabled`, `discover_with_serper`, timeouts, chatbot keywords).
- Set `SERPER_API_KEY` in `.env` (see `.env.example`).

### Google Maps Enrichment (Week 2)
- Google Maps enrichment runs after website enrichment (best effort, non-fatal).
- Configure behavior in `config/sources.yaml` under `sources.google_maps`:
  - `enabled`, `timeout_seconds`, `max_retries`, `min_name_match_score`, `region`, `language`
- Set `GOOGLE_MAPS_API_KEY` in `.env` (see `.env.example`).
- Candidate matching rules:
  - company-name match is required
  - location matching is optional and only applied when usable location is provided
- Location behavior:
  - if location is missing, matching runs name-only
  - if location is invalid/unstructured, API normalization is attempted
  - if normalization fails, matching still runs name-only
  - when a better canonical location is resolved from Google, it is written back to `location`

### Enrichment History and Conflict Resolution
- Final canonical fields remain: `website`, `email`, `phone`, `location`.
- Each lead now includes `enrichment_history` with:
  - `candidates` per field from `input`, `website_enrichment`, and `google_maps`
  - `decisions` per field with chosen source/value and tie-break metadata
  - `stage_errors` for non-fatal enrichment failures
- Conflict policy:
  - prefer highest-confidence validated candidate
  - on website ties, prefer verified Google Maps candidate
  - otherwise keep current canonical value on tie
- Advanced parser additions:
  - JSON-LD (`application/ld+json`) contact extraction is used alongside HTML text/link parsing
  - contact-like pages (`/contact`, `/about`, `/team`, `/agents`) are fetched opportunistically
  - email normalization rejects disposable domains; phone normalization prefers E.164 when available
- Run summary now includes quality metrics:
  - `schema_contacts_used`
  - `email_disposable_rejected`
  - `multi_page_fetch_success`
  - `phone_e164_valid_rate`

## API Endpoints

These endpoints trigger the same Week 1 ingestion pipeline as the CLI.

### Submit Job
- `POST /jobs` (multipart form)

Request form fields:
- `file`: dataset upload
- `input_format` (optional, default `csv`): `csv | json | propflux`

Example:

```bash
curl -s -X POST "http://127.0.0.1:8000/jobs" \
  -F "file=@data/leads.csv" \
  -F "input_format=csv"
```

Response:
- `{ "job_id": "<job_id>", "status": "processing" }`

### Poll Status
- `GET /jobs/{job_id}`

### Fetch Results
- `GET /jobs/{job_id}/results`

Behavior:
- If not completed: HTTP `202` with `{ "job_id": "...", "status": "<processing|uploaded|...>" }`
- If completed: HTTP `200` with `{ "job_id": "...", "status": "completed", "leads": [ ... ] }`
- If failed: HTTP `500` with `{ "job_id": "...", "status": "failed", "error": "..." }`

## Notes

Project scope and goals are defined in `PROJECT_NOTE.md`.
