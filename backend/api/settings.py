from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.ingestion import _load_sources_config
from backend.core.storage_sqlite import (
    activate_settings_profile,
    get_active_settings_profile,
    init_db,
    list_settings_profiles,
    upsert_settings_profile,
)

router = APIRouter(prefix="/settings", tags=["settings"])

DB_PATH = Path("data") / "propintel.sqlite"
DEFAULT_CONFIG_PATH = Path("config") / "sources.yaml"


class SettingsPayload(BaseModel):
    name: str = Field(default="custom")
    payload: dict[str, Any]
    activate: bool = Field(default=True)


class ActivatePayload(BaseModel):
    name: str


def _validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["settings payload must be an object"]
    for key in ("input", "website", "google_maps", "scoring"):
        if key in payload and not isinstance(payload[key], dict):
            errors.append(f"{key} must be an object")
    scoring = payload.get("scoring")
    if isinstance(scoring, dict):
        weights = scoring.get("weights")
        if weights is not None and not isinstance(weights, dict):
            errors.append("scoring.weights must be an object")
    return errors


@router.get("")
def get_settings() -> dict[str, Any]:
    init_db(DB_PATH)
    active = get_active_settings_profile(DB_PATH)
    default_payload = _load_sources_config(DEFAULT_CONFIG_PATH)
    profiles = list_settings_profiles(DB_PATH)
    return {
        "active": active if active is not None else {"name": "default", "payload": default_payload},
        "profiles": [{"name": p["name"], "is_active": p["is_active"], "updated_at": p["updated_at"]} for p in profiles],
    }


@router.post("/validate")
def validate_settings(payload: dict[str, Any]) -> dict[str, Any]:
    errors = _validate_payload(payload)
    return {"ok": len(errors) == 0, "errors": errors}


@router.put("")
def save_settings(body: SettingsPayload) -> dict[str, Any]:
    errors = _validate_payload(body.payload)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    upsert_settings_profile(
        DB_PATH,
        name=body.name.strip() or "custom",
        payload=body.payload,
        activate=bool(body.activate),
    )
    active = get_active_settings_profile(DB_PATH)
    return {"ok": True, "active": active}


@router.post("/activate")
def activate_settings(body: ActivatePayload) -> dict[str, Any]:
    ok = activate_settings_profile(DB_PATH, name=body.name)
    if not ok:
        raise HTTPException(status_code=404, detail="settings profile not found")
    return {"ok": True, "name": body.name}
