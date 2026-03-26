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
