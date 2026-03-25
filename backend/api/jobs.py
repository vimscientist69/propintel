from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.ingestion import run_ingestion

router = APIRouter(prefix="/jobs", tags=["jobs"])

DATA_DIR = Path("data")
JOB_DIR = DATA_DIR / "jobs"
OUTPUT_DIR = Path("output") / "jobs"


class CreateJobRequest(BaseModel):
    # Job ID returned from POST /upload.
    job_id: str | None = None
    # Optional overrides.
    input_format: str | None = None
    config_path: str | None = None


def _job_meta_path(job_id: str) -> Path:
    return JOB_DIR / f"{job_id}.json"


def _load_job_meta(job_id: str) -> dict[str, Any]:
    meta_path = _job_meta_path(job_id)
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="job not found")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _save_job_meta(job_id: str, meta: dict[str, Any]) -> None:
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    _job_meta_path(job_id).write_text(json.dumps(meta, indent=2), encoding="utf-8")


@router.post("")
def create_job(payload: CreateJobRequest) -> dict[str, Any]:
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    job_id = payload.job_id or str(uuid4())

    meta = _load_job_meta(job_id) if payload.job_id else {
        "job_id": job_id,
        "status": "uploaded",
        "input_path": None,
        "input_format": payload.input_format or "csv",
        "config_path": payload.config_path or "config/sources.yaml",
    }

    if meta.get("input_path") is None:
        raise HTTPException(
            status_code=400,
            detail="job must be created from POST /upload (missing input_path)",
        )

    if payload.input_format:
        meta["input_format"] = payload.input_format
    if payload.config_path:
        meta["config_path"] = payload.config_path

    if meta.get("status") == "completed":
        return meta

    meta["status"] = "processing"
    _save_job_meta(job_id, meta)

    out_dir = OUTPUT_DIR / job_id
    summary_path = out_dir / "summary.json"

    try:
        summary = run_ingestion(
            input_path=meta["input_path"],
            input_format=meta.get("input_format") or "csv",
            config_path=meta.get("config_path") or "config/sources.yaml",
            output_summary_path=summary_path,
        )
        meta["status"] = "completed"
        meta["results"] = summary["output"]
        meta["counts"] = summary["counts"]
        _save_job_meta(job_id, meta)
        return meta
    except Exception as exc:  # noqa: BLE001 (FastAPI surface error)
        meta["status"] = "failed"
        meta["error"] = str(exc)
        _save_job_meta(job_id, meta)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    return _load_job_meta(job_id)
