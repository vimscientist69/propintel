from uuid import uuid4

from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("")
def create_job() -> dict[str, str]:
    return {"job_id": str(uuid4()), "status": "queued"}


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, str]:
    return {"job_id": job_id, "status": "pending"}
