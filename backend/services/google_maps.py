from __future__ import annotations

import os
import time
from difflib import SequenceMatcher
from typing import Any


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def _normalize_str(value: Any) -> str:
    return str(value or "").strip()


def _is_usable_location(location: str | None) -> bool:
    return bool(location and len(location.strip()) >= 3)


def _similarity(a: str, b: str) -> float:
    a_norm = _normalize_str(a).lower()
    b_norm = _normalize_str(b).lower()
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def _request_json_with_retries(
    *,
    method: str,
    url: str,
    params: dict[str, Any],
    timeout_seconds: int,
    max_retries: int,
) -> dict[str, Any] | None:
    import requests

    attempts = max(0, int(max_retries)) + 1
    delay_seconds = 0.5

    for attempt in range(attempts):
        try:
            if method == "GET":
                response = requests.get(url, params=params, timeout=timeout_seconds)
            else:
                response = requests.post(url, json=params, timeout=timeout_seconds)

            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < attempts - 1:
                    time.sleep(delay_seconds)
                    delay_seconds *= 2
                    continue
                return None

            if not response.ok:
                return None

            payload = response.json()
            if not isinstance(payload, dict):
                return None
            return payload
        except Exception:
            if attempt < attempts - 1:
                time.sleep(delay_seconds)
                delay_seconds *= 2
                continue
            return None

    return None


def normalize_location(
    raw_location: str | None,
    *,
    google_maps_api_key: str,
    timeout_seconds: int,
    max_retries: int,
    region: str | None = None,
    language: str | None = None,
) -> str | None:
    if not _is_usable_location(raw_location):
        return None

    params: dict[str, Any] = {
        "address": _normalize_str(raw_location),
        "key": google_maps_api_key,
    }
    if region:
        params["region"] = region
    if language:
        params["language"] = language

    payload = _request_json_with_retries(
        method="GET",
        url="https://maps.googleapis.com/maps/api/geocode/json",
        params=params,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )
    if not payload:
        return None

    results = payload.get("results") or []
    if not results:
        return None

    first = results[0]
    formatted = _normalize_str(first.get("formatted_address"))
    return formatted or None


def search_places(
    company_name: str,
    *,
    location: str | None,
    google_maps_api_key: str,
    timeout_seconds: int,
    max_retries: int,
    region: str | None = None,
    language: str | None = None,
) -> list[dict[str, Any]]:
    query = _normalize_str(company_name)
    if location:
        query = f"{query} {_normalize_str(location)}"

    params: dict[str, Any] = {
        "query": query,
        "key": google_maps_api_key,
    }
    if region:
        params["region"] = region
    if language:
        params["language"] = language

    payload = _request_json_with_retries(
        method="GET",
        url="https://maps.googleapis.com/maps/api/place/textsearch/json",
        params=params,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )
    if not payload:
        return []
    return payload.get("results") or []


def get_place_details(
    place_id: str,
    *,
    google_maps_api_key: str,
    timeout_seconds: int,
    max_retries: int,
    language: str | None = None,
) -> dict[str, Any] | None:
    params: dict[str, Any] = {
        "place_id": place_id,
        "fields": "name,formatted_address,website,formatted_phone_number,international_phone_number",
        "key": google_maps_api_key,
    }
    if language:
        params["language"] = language

    payload = _request_json_with_retries(
        method="GET",
        url="https://maps.googleapis.com/maps/api/place/details/json",
        params=params,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )
    if not payload:
        return None
    result = payload.get("result")
    return result if isinstance(result, dict) else None


def match_best_candidate(
    candidates: list[dict[str, Any]],
    lead: dict[str, Any],
    *,
    min_name_match_score: float,
    normalized_location: str | None,
) -> dict[str, Any] | None:
    company_name = _normalize_str(lead.get("company_name"))
    if not company_name:
        return None

    require_location_match = _is_usable_location(normalized_location)
    location_norm = _normalize_str(normalized_location).lower()

    best_candidate: dict[str, Any] | None = None
    best_score = -1.0

    for c in candidates:
        cand_name = _normalize_str(c.get("name"))
        cand_addr = _normalize_str(c.get("formatted_address")).lower()
        name_score = _similarity(company_name, cand_name)
        if name_score < float(min_name_match_score):
            continue

        score = name_score
        if require_location_match:
            # Optional location matching: only influences score when location is provided.
            if location_norm and location_norm in cand_addr:
                score += 0.15
            else:
                score -= 0.05

        if score > best_score:
            best_score = score
            best_candidate = c

    return best_candidate


def enrich_lead_from_google_maps(
    lead: dict[str, Any],
    google_maps_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = dict(lead)
    cfg = google_maps_config or {}
    if not cfg.get("enabled", False):
        return enriched

    _load_env()
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        enriched["google_maps_error"] = "missing_api_key"
        return enriched

    timeout_seconds = int(cfg.get("timeout_seconds", 8))
    max_retries = int(cfg.get("max_retries", 2))
    min_name_match_score = float(cfg.get("min_name_match_score", 0.5))
    region = _normalize_str(cfg.get("region")) or None
    language = _normalize_str(cfg.get("language")) or None

    company_name = _normalize_str(enriched.get("company_name"))
    if not company_name:
        return enriched

    original_location = _normalize_str(enriched.get("location")) or None
    normalized_location = normalize_location(
        original_location,
        google_maps_api_key=api_key,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        region=region,
        language=language,
    ) if _is_usable_location(original_location) else None

    # If location exists but is invalid/unusable, we continue name-only search.
    candidates = search_places(
        company_name,
        location=normalized_location,
        google_maps_api_key=api_key,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        region=region,
        language=language,
    )
    if not candidates and normalized_location:
        candidates = search_places(
            company_name,
            location=None,
            google_maps_api_key=api_key,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            region=region,
            language=language,
        )

    chosen = match_best_candidate(
        candidates,
        enriched,
        min_name_match_score=min_name_match_score,
        normalized_location=normalized_location,
    )
    if not chosen:
        return enriched

    place_id = _normalize_str(chosen.get("place_id"))
    if not place_id:
        return enriched

    details = get_place_details(
        place_id,
        google_maps_api_key=api_key,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        language=language,
    )
    if not details:
        return enriched

    website = _normalize_str(details.get("website")) or None
    phone = (
        _normalize_str(details.get("international_phone_number"))
        or _normalize_str(details.get("formatted_phone_number"))
        or None
    )
    formatted_address = _normalize_str(details.get("formatted_address")) or None

    if not enriched.get("website") and website:
        enriched["website"] = website
    if not enriched.get("phone") and phone:
        enriched["phone"] = phone

    # If location is missing, invalid, or unstructured, prefer canonical formatted address.
    if formatted_address:
        if not _is_usable_location(original_location) or normalized_location is None:
            enriched["location"] = formatted_address
        elif not _normalize_str(original_location):
            enriched["location"] = formatted_address
        else:
            # Keep normalized location if it exists; otherwise use place details.
            enriched["location"] = normalized_location or formatted_address

    source = _normalize_str(enriched.get("source"))
    if source:
        if "google_maps" not in source:
            enriched["source"] = f"{source},google_maps"
    else:
        enriched["source"] = "google_maps"

    return enriched

