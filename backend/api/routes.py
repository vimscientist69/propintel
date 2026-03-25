from __future__ import annotations

from fastapi import FastAPI

from backend.api.jobs import router as jobs_router

app = FastAPI(title="PropIntel API", version="0.1.0")
app.include_router(jobs_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
