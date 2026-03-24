from fastapi import FastAPI

from backend.api.jobs import router as jobs_router

app = FastAPI(title="PropIntel API", version="0.1.0")
app.include_router(jobs_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/upload")
def upload_placeholder() -> dict[str, str]:
    return {"status": "accepted", "message": "Upload endpoint scaffolded"}


@app.get("/results/{job_id}")
def get_results(job_id: str) -> dict[str, str]:
    return {"job_id": job_id, "status": "not_ready"}
