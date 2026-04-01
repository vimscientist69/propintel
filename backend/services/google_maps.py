from __future__ import annotations

import os
import time
from difflib import SequenceMatcher
from typing import Any

from backend.core.logging_utils import get_logger


logger = get_logger(__name__)


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
        logger.debug("Google Maps normalize_location skipped: unusable input")
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
        logger.warning("Google Maps geocoding returned no payload for location='{}'", raw_location)
        return None

    results = payload.get("results") or []
    if not results:
        logger.info("Google Maps geocoding returned no results for location='{}'", raw_location)
        return None

    first = results[0]
    formatted = _normalize_str(first.get("formatted_address"))
    logger.debug(
        "Google Maps normalized location '{}' -> '{}'",
        raw_location,
        formatted or "<none>",
    )
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
    import requests

    query = _normalize_str(company_name)
    if location:
        query = f"{query} {_normalize_str(location)}"

    body: dict[str, Any] = {
        "textQuery": query,
        "pageSize": 5,
    }
    if region:
        body["regionCode"] = region
    if language:
        body["languageCode"] = language

    attempts = max(0, int(max_retries)) + 1
    delay_seconds = 0.5
    payload: dict[str, Any] | None = None

    for attempt in range(attempts):
        try:
            response = requests.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": google_maps_api_key,
                    "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.name",
                },
                json=body,
                timeout=timeout_seconds,
            )
            if response.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    "Google Maps Text Search retryable status={} attempt={}/{} query='{}'",
                    response.status_code,
                    attempt + 1,
                    attempts,
                    query,
                )
                if attempt < attempts - 1:
                    time.sleep(delay_seconds)
                    delay_seconds *= 2
                    continue
                return []
            if not response.ok:
                logger.warning(
                    "Google Maps Text Search failed status={} query='{}'",
                    response.status_code,
                    query,
                )
                return []
            payload = response.json()
            if not isinstance(payload, dict):
                return []
            break
        except Exception:
            logger.exception(
                "Google Maps Text Search exception attempt={}/{} query='{}'",
                attempt + 1,
                attempts,
                query,
            )
            if attempt < attempts - 1:
                time.sleep(delay_seconds)
                delay_seconds *= 2
                continue
            return []

    if not payload:
        logger.info("Google Maps Text Search returned empty payload query='{}'", query)
        return []

    places = payload.get("places") or []
    normalized: list[dict[str, Any]] = []
    for place in places:
        if not isinstance(place, dict):
            continue
        resource_name = _normalize_str(place.get("name"))
        place_id = _normalize_str(place.get("id"))
        if not place_id and resource_name.startswith("places/"):
            place_id = resource_name.split("/", 1)[1]
        display_name = (
            _normalize_str((place.get("displayName") or {}).get("text"))
            if isinstance(place.get("displayName"), dict)
            else _normalize_str(place.get("displayName"))
        )
        normalized.append(
            {
                "name": display_name,
                "formatted_address": _normalize_str(place.get("formattedAddress")),
                "place_id": place_id,
            }
        )

    logger.info(
        "Google Maps Text Search candidates={} query='{}'",
        len(normalized),
        query,
    )
    return normalized


def get_place_details(
    place_id: str,
    *,
    google_maps_api_key: str,
    timeout_seconds: int,
    max_retries: int,
    language: str | None = None,
) -> dict[str, Any] | None:
    import requests

    params: dict[str, Any] = {}
    if language:
        params["languageCode"] = language

    attempts = max(0, int(max_retries)) + 1
    delay_seconds = 0.5

    for attempt in range(attempts):
        try:
            response = requests.get(
                f"https://places.googleapis.com/v1/places/{place_id}",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": google_maps_api_key,
                    "X-Goog-FieldMask": "id,displayName,formattedAddress,websiteUri,nationalPhoneNumber,internationalPhoneNumber",
                },
                params=params,
                timeout=timeout_seconds,
            )
            if response.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    "Google Maps Place Details retryable status={} place_id={} attempt={}/{}",
                    response.status_code,
                    place_id,
                    attempt + 1,
                    attempts,
                )
                if attempt < attempts - 1:
                    time.sleep(delay_seconds)
                    delay_seconds *= 2
                    continue
                return None
            if not response.ok:
                logger.warning(
                    "Google Maps Place Details failed status={} place_id={}",
                    response.status_code,
                    place_id,
                )
                return None
            payload = response.json()
            if not isinstance(payload, dict):
                logger.warning("Google Maps Place Details invalid JSON for place_id={}", place_id)
                return None
            result = {
                "website": _normalize_str(payload.get("websiteUri")),
                "formatted_phone_number": _normalize_str(payload.get("nationalPhoneNumber")),
                "international_phone_number": _normalize_str(payload.get("internationalPhoneNumber")),
                "formatted_address": _normalize_str(payload.get("formattedAddress")),
            }
            logger.debug(
                "Google Maps Place Details success place_id={} website={} phone={} address={}",
                place_id,
                bool(result["website"]),
                bool(result["formatted_phone_number"] or result["international_phone_number"]),
                bool(result["formatted_address"]),
            )
            return result
        except Exception:
            logger.exception(
                "Google Maps Place Details exception place_id={} attempt={}/{}",
                place_id,
                attempt + 1,
                attempts,
            )
            if attempt < attempts - 1:
                time.sleep(delay_seconds)
                delay_seconds *= 2
                continue
            return None

    return None


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
        logger.debug("Google Maps enrichment disabled")
        return enriched

    _load_env()
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        enriched["google_maps_error"] = "missing_api_key"
        logger.warning("Google Maps enrichment skipped: missing GOOGLE_MAPS_API_KEY")
        return enriched
    timeout_seconds = int(cfg.get("timeout_seconds", 8))
    max_retries = int(cfg.get("max_retries", 2))
    min_name_match_score = float(cfg.get("min_name_match_score", 0.5))
    region = _normalize_str(cfg.get("region")) or None
    language = _normalize_str(cfg.get("language")) or None

    company_name = _normalize_str(enriched.get("company_name"))
    if not company_name:
        logger.debug("Google Maps enrichment skipped: missing company_name")
        return enriched

    original_location = _normalize_str(enriched.get("location")) or None
    logger.info(
        "Google Maps enrichment start company='{}' has_location={} has_website={}",
        company_name,
        bool(original_location),
        bool(_normalize_str(enriched.get("website"))),
    )
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
        logger.info(
            "Google Maps fallback to name-only search company='{}' normalized_location='{}'",
            company_name,
            normalized_location,
        )
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
        logger.info("Google Maps no candidate matched company='{}'", company_name)
        return enriched

    place_id = _normalize_str(chosen.get("place_id"))
    if not place_id:
        logger.warning("Google Maps candidate missing place_id company='{}'", company_name)
        return enriched

    details = get_place_details(
        place_id,
        google_maps_api_key=api_key,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        language=language,
    )
    if not details:
        logger.info("Google Maps no place details place_id={} company='{}'", place_id, company_name)
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

    logger.info(
        "Google Maps enrichment success company='{}' website_set={} phone_set={} location_updated={}",
        company_name,
        bool(enriched.get("website")),
        bool(enriched.get("phone")),
        _normalize_str(enriched.get("location")) != _normalize_str(original_location),
    )
    return enriched

