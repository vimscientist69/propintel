# 🧠 PropIntel

PropIntel is a production-style **real estate lead intelligence platform** that ingests raw lead datasets, enriches them from external sources, verifies contact quality, and ranks lead readiness for outreach.

Built as a portfolio project to demonstrate practical delivery across backend systems, data workflows, and operator-friendly product UI.

### Why clients pick this (quick pitch)
- You get a repeatable lead intelligence workflow: upload files, run jobs, monitor progress, and export ranked leads.
- It is resilient for long-running processing: batching, partial result persistence, termination controls, and resume support.
- It is operator-friendly: dashboard tabs for analytics, job history, exploration, and runtime settings profiles.

---

## 🎯 Features

- **Flexible ingestion**: CSV, JSON, and PropFlux-style inputs.
- **Website enrichment**: contact extraction, chatbot detection, freshness signals, website speed scoring.
- **Google Maps enrichment**: business matching, phone/website/location augmentation.
- **Conflict resolution**: source-aware candidate merging with enrichment history.
- **Contact verification**: `verified` / `likely` / `low` quality model.
- **Lead scoring**: configurable scoring engine with explainable `lead_reason`.
- **Batch processing**: incremental writes to DB, lower memory pressure, partial visibility.
- **Resumable jobs**: failed/terminated jobs can be resumed.
- **Concurrency + rate limiting**: provider-aware limits for Serper and Google Maps.
- **Responsive dashboard**: control panel, analytics, job history, data explorer, engine settings.

---

## 📊 Current State

PropIntel currently runs end-to-end as a complete enrichment pipeline + dashboard system with:
- strict config schema validation
- SQLite-backed job/result persistence
- batch lifecycle tracking (`pending/processing/completed/failed/terminated`)
- partial results during processing
- stop + resume controls
- provider-aware runtime controls for concurrency and request pacing

Ongoing work is focused on deployment and post-MVP extensions (integrations, additional enrichment sources, and operational hardening).

---

## 📋 Requirements

- Python 3.11+
- Node.js 20+ (for dashboard build/dev)
- API keys for optional external enrichment:
  - `SERPER_API_KEY`
  - `GOOGLE_MAPS_API_KEY`

---

## 🚀 Quick Start

### 1. Setup backend

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

Create `.env` from `.env.example` and fill keys if you want external enrichment:

```bash
cp .env.example .env
```

### 3. Start API

```bash
python runner.py api --host 127.0.0.1 --port 8000 --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

### 4. Start dashboard

```bash
cd frontend/dashboard
npm install
npm run dev
```

Open:
- Dashboard: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8000`

---

## 🖥 CLI Usage

`runner.py` supports:
- `api` — start FastAPI server
- `run` — execute pipeline locally and export artifacts

Examples:

```bash
# Start API
python runner.py api --host 0.0.0.0 --port 8080 --reload --log-level debug

# Run pipeline with CSV input
python runner.py run --input data/leads.csv --input-format csv --config config/sources.yaml --output output --log-level info

# Run pipeline with PropFlux-like JSON
python runner.py run --input data/propflux_export.json --input-format propflux
```

---

## Output (where results go)

CLI runs create a timestamped folder under `output/`:

`output/<timestamp>/`

Artifacts per run:
- `leads_<timestamp>.json`
- `leads_<timestamp>.csv`
- `rejected_rows_<timestamp>.json`
- `run_summary_<timestamp>.json`
- logs in `logs/propintel_<timestamp>.log`

---

## Client-Facing Walkthrough (how this delivers results)

PropIntel is built for repeatable operations, not one-off scripts.

### How it works
1. A dataset is uploaded (`POST /jobs`) or run through CLI.
2. Input rows are mapped/validated, normalized, deduplicated.
3. Job is split into batches and persisted in SQLite (`job_batches`).
4. Enrichment runs with configurable concurrency and provider-aware rate limits.
5. Each completed batch writes leads immediately to DB (partial results available).
6. Verification, conflict resolution, and scoring produce final lead intelligence fields.
7. Dashboard/API surfaces telemetry, progress, outputs, and resume/termination controls.

---

## Dashboard Documentation (what to click + what to expect)

The dashboard lives in `frontend/dashboard/` and talks to the FastAPI backend.

### Main Control Panel
- Upload dataset (`csv | json | propflux`)
- Start, terminate, and resume jobs
- See live progress (started/completed batches, row progress)
- See recent jobs and quick-select active job

### Latest Listings
- Filter by score, contact quality, chatbot signal, freshness signal
- Export active job results (JSON/CSV once completed)
- Shows partial results while job is processing

### Analytics
- Total jobs, completed jobs
- Average lead score
- Verified contact rate

### Job History
- Full job listing with statuses and run metadata
- Mobile-friendly card layout for non-desktop widths

### Data Explorer
- Select a job and inspect rows in detail
- Live reload + responsive card/table behavior

### Engine Settings
- Validate and save profile JSON
- Activate/delete profiles
- Active profile is used by job processing

---

## API Endpoints (used by dashboard + integrations)

### Jobs
- `POST /jobs` — create job from uploaded file
- `GET /jobs` — paginated jobs list (`limit`, `offset`, optional `status`)
- `GET /jobs/{job_id}` — status + counts + batch progress
- `POST /jobs/{job_id}/terminate` — stop running job
- `POST /jobs/{job_id}/resume` — resume failed/terminated job
- `GET /jobs/{job_id}/batches` — batch lifecycle rows

### Results
- `GET /jobs/{job_id}/results` — returns current rows (`partial=true` until completed)
- `GET /jobs/{job_id}/rejected` — rejected rows for the job
- `GET /jobs/{job_id}/export?format=csv|json` — export completed results

### Settings Profiles
- `GET /settings`
- `POST /settings/validate`
- `PUT /settings`
- `POST /settings/activate`
- `DELETE /settings/{name}`

---

## Runtime Config (high-level)

Configured in `config/sources.yaml` or via Engine Settings profiles:
- `input` mapping/validation rules
- `website` enrichment controls
- `google_maps` enrichment controls
- `scoring` weights and score behavior
- `runtime` batching + worker concurrency + provider rate limits

Minimal runtime defaults are included; advanced knobs are optional.

---

## Testing

Run backend tests:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Build dashboard:

```bash
cd frontend/dashboard
npm run build
```

CI workflow is included at `.github/workflows/ci.yml` for backend tests + frontend build.

---

## Run Locally with Docker

This runs the same split architecture used in Fly deployment:
- backend container (`propintel-api`) on internal Docker network only
- frontend container (`propintel-web`) exposed on localhost

### 1) Build images

```bash
docker build -f deploy/fly/backend.Dockerfile -t propintel-api:local .
docker build -f deploy/fly/frontend.Dockerfile -t propintel-web:local .
```

### 2) Create a Docker network

```bash
docker network create propintel-net
```

### 3) Run backend (internal only)

```bash
docker run -d \
  --name propintel-api \
  --network propintel-net \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  propintel-api:local
```

### 4) Run frontend (public)

```bash
docker run -d \
  --name propintel-web \
  --network propintel-net \
  -p 8080:8080 \
  propintel-web:local
```

Open: `http://localhost:8080`

### 5) Stop and clean up

```bash
docker rm -f propintel-web propintel-api
docker network rm propintel-net
```

Notes:
- `deploy/fly/nginx.conf` routes `/jobs`, `/settings`, and `/health` to `propintel-api`.
- Keep `.env` local only; do not commit secrets.

---

## Deployment (Fly.io)

Deployment is configured for a **two-app Fly.io topology**:
- `propintel-web` (public): serves the React dashboard
- `propintel-api` (private/internal): serves FastAPI + SQLite

The frontend app reverse-proxies `/jobs`, `/settings`, and `/health` to the internal backend host.

Deployment assets:
- `deploy/fly/backend.Dockerfile`
- `deploy/fly/frontend.Dockerfile`
- `deploy/fly/nginx.conf`
- `deploy/fly/backend.fly.toml`
- `deploy/fly/frontend.fly.toml`

### 1) Backend app (internal)

```bash
# Create app (one-time)
fly apps create propintel-api

# Create persistent volume for SQLite/uploads (one-time)
fly volumes create propintel_data --size 1 --region jnb --app propintel-api

# Set backend secrets
fly secrets set SERPER_API_KEY=... GOOGLE_MAPS_API_KEY=... -a propintel-api

# Deploy backend
fly deploy -c deploy/fly/backend.fly.toml
```

After first deploy, remove any public IPs from backend so it remains internal-only:

```bash
fly ips list -a propintel-api
fly ips release <IP_ADDRESS> -a propintel-api
```

### 2) Frontend app (public)

```bash
# Create app (one-time)
fly apps create propintel-web

# Deploy frontend
fly deploy -c deploy/fly/frontend.fly.toml
```

### Important notes

- Backend is expected at `http://propintel-api.internal:8000` (used by `deploy/fly/nginx.conf`).
- If you rename the backend app, update `deploy/fly/nginx.conf` accordingly.
- Frontend does not require public API URL env var in this topology; browser calls same-origin paths, nginx proxies internally.

---

## Security Notes

- Never commit real API keys or `.env` files.
- Use `.env.example` as the template.
- Rotate any development keys before public release.

---

Built with love for practical lead intelligence and clean, reliable data workflows.
