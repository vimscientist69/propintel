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
  - `python runner.py run --input data/leads.csv --input-format csv --config config/sources.yaml --output output/run_summary.json --log-level info`
- Run pipeline with PropFlux input:
  - `python runner.py run --input data/propflux_export.json --input-format propflux`

All CLI runs log to `logs/propintel_YYYYMMDD_HHMMSS.log` and stderr via `loguru`.

### Pipeline Outputs (CLI `run`)
Given `--output <path>`, the CLI writes into `dirname(<path>)`:

- `leads.json`
- `leads.csv`
- `rejected_rows.json`
- `<path>`: ingestion summary JSON

## API Endpoints

These endpoints trigger the same Week 1 ingestion pipeline as the CLI.

### Upload
- `POST /upload` (multipart form)

Example:

```bash
curl -s -X POST "http://127.0.0.1:8000/upload" \
  -F "file=@data/leads.csv" \
  -F "input_format=csv" \
  -F "config_path=config/sources.yaml"
```

This returns a `job_id`.

### Create / Run Job
- `POST /jobs` (JSON body)

Example:

```bash
curl -s -X POST "http://127.0.0.1:8000/jobs" \
  -H "Content-Type: application/json" \
  -d '{"job_id":"<job_id>"}'
```

### Check Status
- `GET /jobs/{job_id}`

### Fetch Results
- `GET /results/{job_id}`

## Notes

Project scope and goals are defined in `PROJECT_NOTE.md`.
