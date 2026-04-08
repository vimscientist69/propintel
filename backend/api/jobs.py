from __future__ import annotations
from concurrent.futures import Future, ThreadPoolExecutor
import csv
import io
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response

from backend.core.ingestion import JobTerminationRequested, ingest_to_structures
from backend.core.parser import CANONICAL_FIELDS
from backend.core.storage_sqlite import (
    create_job,
    get_active_settings_profile,
    get_job,
    get_leads,
    init_db,
    insert_leads,
    list_jobs,
    update_job_completed,
    update_job_failed,
    update_job_processing_started,
    update_job_terminated,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])

DB_PATH = Path("data") / "propintel.sqlite"
DEFAULT_CONFIG_PATH = Path("config") / "sources.yaml"
UPLOAD_DIR = Path("data") / "uploads"

EXECUTOR = ThreadPoolExecutor(max_workers=4)
JOB_CANCEL_EVENTS: dict[str, threading.Event] = {}
JOB_FUTURES: dict[str, Future[Any]] = {}


def _input_extension(input_format: str) -> str:
    normalized = input_format.strip().lower()
    if normalized == "csv":
        return ".csv"
    # json + propflux are both JSON payloads for this MVP.
    return ".json"


def _process_job(job_id: str, *, input_path: Path, input_format: str) -> None:
    try:
        cancel_event = JOB_CANCEL_EVENTS.setdefault(job_id, threading.Event())
        active_profile = get_active_settings_profile(DB_PATH)
        if active_profile and isinstance(active_profile.get("payload"), dict):
            from backend.core.ingestion import ingest_to_structures_with_sources_config

            leads, rejected, summary = ingest_to_structures_with_sources_config(
                input_path=input_path,
                input_format=input_format,
                sources_cfg=active_profile["payload"],
                should_stop=cancel_event.is_set,
            )
        else:
            leads, rejected, summary = ingest_to_structures(
                input_path=input_path,
                input_format=input_format,
                config_path=DEFAULT_CONFIG_PATH,
                should_stop=cancel_event.is_set,
            )

        if cancel_event.is_set():
            update_job_terminated(DB_PATH, job_id=job_id)
            return
        insert_leads(DB_PATH, job_id=job_id, leads=leads)
        update_job_completed(
            DB_PATH,
            job_id=job_id,
            counts=summary["counts"],
            rejected_rows=rejected,
        )
    except JobTerminationRequested:
        update_job_terminated(DB_PATH, job_id=job_id)
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
    finally:
        JOB_FUTURES.pop(job_id, None)
        JOB_CANCEL_EVENTS.pop(job_id, None)


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

    future = EXECUTOR.submit(
        _process_job,
        job_id,
        input_path=input_path,
        input_format=normalized_format,
    )
    JOB_FUTURES[job_id] = future

    return {"job_id": job_id, "status": "processing"}


@router.get("")
def list_jobs_endpoint(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
) -> dict[str, Any]:
    init_db(DB_PATH)
    items, total = list_jobs(
        DB_PATH,
        limit=limit,
        offset=offset,
        status=status,
    )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


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


@router.post("/{job_id}/terminate")
def terminate_job(job_id: str) -> dict[str, Any]:
    job = get_job(DB_PATH, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    status = str(job.get("status") or "")
    if status in {"completed", "failed", "terminated"}:
        raise HTTPException(status_code=409, detail=f"job already {status}")

    cancel_event = JOB_CANCEL_EVENTS.get(job_id)
    if cancel_event is None:
        cancel_event = threading.Event()
        JOB_CANCEL_EVENTS[job_id] = cancel_event
    cancel_event.set()

    future = JOB_FUTURES.get(job_id)
    if future is not None:
        future.cancel()

    update_job_terminated(DB_PATH, job_id=job_id)
    return {"job_id": job_id, "status": "terminated"}


@router.get("/{job_id}/results")
def get_results(job_id: str):
    job = get_job(DB_PATH, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    status = job["status"]
    if status != "completed":
        if status in {"failed", "terminated"}:
            return JSONResponse(
                status_code=409,
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


@router.get("/{job_id}/rejected")
def get_rejected_rows(job_id: str) -> dict[str, Any]:
    job = get_job(DB_PATH, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job_id,
        "status": job["status"],
        "rejected_rows": job.get("rejected_rows") or [],
    }


@router.get("/{job_id}/export")
def export_results(job_id: str, format: str = Query("json")) -> Response:
    job = get_job(DB_PATH, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="job not completed")

    leads = get_leads(DB_PATH, job_id=job_id)
    export_format = format.strip().lower()
    if export_format == "json":
        body = JSONResponse(content=leads).body
        headers = {"Content-Disposition": f'attachment; filename="propintel_{job_id}.json"'}
        return Response(content=body, media_type="application/json", headers=headers)

    if export_format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(CANONICAL_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            writer.writerow({k: lead.get(k) for k in CANONICAL_FIELDS})
        headers = {"Content-Disposition": f'attachment; filename="propintel_{job_id}.csv"'}
        return Response(content=buf.getvalue(), media_type="text/csv", headers=headers)

    raise HTTPException(status_code=400, detail="unsupported export format")
