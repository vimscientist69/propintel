from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import File, Form, HTTPException, UploadFile
from fastapi import FastAPI

from backend.api.jobs import router as jobs_router
from backend.api.jobs import JOB_DIR

app = FastAPI(title="PropIntel API", version="0.1.0")
app.include_router(jobs_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/upload")
def upload_dataset(
    file: UploadFile = File(...),
    input_format: str = Form("csv"),
    config_path: str = Form("config/sources.yaml"),
) -> dict[str, str]:
    JOB_DIR.mkdir(parents=True, exist_ok=True)

    job_id = str(uuid4())
    upload_dir = Path("data") / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    fmt = input_format.strip().lower()
    ext = ".csv" if fmt == "csv" else ".json"
    input_path = upload_dir / f"{job_id}{ext}"

    input_bytes = file.file.read()
    input_path.write_bytes(input_bytes)

    meta = {
        "job_id": job_id,
        "status": "uploaded",
        "input_path": str(input_path),
        "input_format": fmt,
        "config_path": config_path,
    }
    (JOB_DIR / f"{job_id}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return {"job_id": job_id, "status": "uploaded"}


@app.get("/results/{job_id}")
def get_results(job_id: str):
    meta_path = JOB_DIR / f"{job_id}.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="job not found")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    status = meta.get("status")
    if status != "completed":
        return {"job_id": job_id, "status": status}

    results = meta.get("results") or {}
    leads_json_path = results.get("leads_json")
    if not leads_json_path:
        leads_json_path = str(Path("output") / "jobs" / job_id / "leads.json")

    leads_path = Path(leads_json_path)
    if not leads_path.exists():
        return {"job_id": job_id, "status": "not_ready"}

    leads = json.loads(leads_path.read_text(encoding="utf-8"))
    return {"job_id": job_id, "status": "completed", "leads": leads}
