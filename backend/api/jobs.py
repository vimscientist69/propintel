from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from backend.core.ingestion import ingest_to_structures
from backend.core.storage_sqlite import (
    create_job,
    get_job,
    get_leads,
    init_db,
    insert_leads,
    update_job_completed,
    update_job_failed,
    update_job_processing_started,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])

DB_PATH = Path("data") / "propintel.sqlite"
DEFAULT_CONFIG_PATH = Path("config") / "sources.yaml"
UPLOAD_DIR = Path("data") / "uploads"

EXECUTOR = ThreadPoolExecutor(max_workers=4)


def _input_extension(input_format: str) -> str:
    normalized = input_format.strip().lower()
    if normalized == "csv":
        return ".csv"
    # json + propflux are both JSON payloads for this MVP.
    return ".json"


def _process_job(job_id: str, *, input_path: Path, input_format: str) -> None:
    try:
        leads, rejected, summary = ingest_to_structures(
            input_path=input_path,
            input_format=input_format,
            config_path=DEFAULT_CONFIG_PATH,
        )

        insert_leads(DB_PATH, job_id=job_id, leads=leads)
        update_job_completed(
            DB_PATH,
            job_id=job_id,
            counts=summary["counts"],
            rejected_rows=rejected,
        )
    except Exception as exc:  # noqa: BLE001
        # Keep the error message human-readable for the dashboard.
        try:
            from loguru import logger

            logger.exception("Job processing failed for job_id={}", job_id)
        except Exception:
            # If loguru isn't available, still persist the failure state.
            pass
        update_job_failed(DB_PATH, job_id=job_id, error=f"{exc}")
        # Avoid printing from library code; logger.exception (above) captures details.


@router.post("")
def submit_job(
    file: UploadFile = File(...),
    input_format: str = Form("csv"),
) -> dict[str, Any]:
    init_db(DB_PATH)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    job_id = str(uuid4())
    normalized_format = input_format.strip().lower()
    ext = _input_extension(normalized_format)

    input_path = UPLOAD_DIR / f"{job_id}{ext}"
    input_bytes = file.file.read()
    input_path.write_bytes(input_bytes)

    create_job(
        DB_PATH,
        job_id=job_id,
        input_format=normalized_format,
        status="uploaded",
    )
    update_job_processing_started(DB_PATH, job_id=job_id)

    EXECUTOR.submit(
        _process_job,
        job_id,
        input_path=input_path,
        input_format=normalized_format,
    )

    return {"job_id": job_id, "status": "processing"}


@router.get("/{job_id}")
def poll_job(job_id: str) -> dict[str, Any]:
    job = get_job(DB_PATH, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    return {
        "job_id": job_id,
        "status": job["status"],
        "counts": job["counts"],
        "error": job["error"],
    }


@router.get("/{job_id}/results")
def get_results(job_id: str):
    job = get_job(DB_PATH, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    status = job["status"]
    if status != "completed":
        if status == "failed":
            return JSONResponse(
                status_code=500,
                content={
                    "job_id": job_id,
                    "status": status,
                    "error": job["error"],
                },
            )
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job_id,
                "status": status,
            },
        )

    leads = get_leads(DB_PATH, job_id=job_id)
    return {"job_id": job_id, "status": "completed", "leads": leads}
