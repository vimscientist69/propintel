from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


TRACKED_FIELDS = ("website", "email", "phone", "location")


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_candidate(
    *,
    field: str,
    source: str,
    value: Any,
    validated: bool,
    confidence: float,
    validation_reason: str,
) -> dict[str, Any]:
    return {
        "field": field,
        "source": source,
        "value": value,
        "validated": validated,
        "confidence": float(confidence),
        "validation_reason": validation_reason,
        "timestamp": _ts(),
    }


def resolve_field_candidates(
    field: str,
    candidates: list[dict[str, Any]],
    *,
    current_value: Any,
    current_source: str = "input",
) -> tuple[Any, dict[str, Any]]:
    if not candidates:
        return current_value, {
            "field": field,
            "chosen_source": current_source,
            "chosen_value": current_value,
            "tie_break_applied": False,
            "tie_break_reason": "no_candidates",
            "alternatives": [],
        }

    valid = [c for c in candidates if c.get("validated") is True]
    pool = valid if valid else candidates

    max_conf = max(float(c.get("confidence", 0.0)) for c in pool)
    top = [c for c in pool if float(c.get("confidence", 0.0)) == max_conf]
    chosen = top[0]
    tie_break_applied = len(top) > 1
    tie_break_reason = "highest_confidence"

    if tie_break_applied:
        # Confirmed policy: prefer google_maps in a tie for website, but only if validated.
        if field == "website":
            gmaps = [
                c
                for c in top
                if c.get("source") == "google_maps" and c.get("validated") is True
            ]
            if gmaps:
                chosen = gmaps[0]
                tie_break_reason = "prefer_google_maps_if_verified"
            else:
                # Keep current canonical when no verified Google Maps winner.
                current_match = [c for c in top if c.get("value") == current_value]
                if current_match:
                    chosen = current_match[0]
                    tie_break_reason = "keep_current_on_tie"
                else:
                    tie_break_reason = "tie_first_candidate"
        else:
            current_match = [c for c in top if c.get("value") == current_value]
            if current_match:
                chosen = current_match[0]
                tie_break_reason = "keep_current_on_tie"
            else:
                tie_break_reason = "tie_first_candidate"

    chosen_value = chosen.get("value")
    decision = {
        "field": field,
        "chosen_source": chosen.get("source", current_source),
        "chosen_value": chosen_value,
        "tie_break_applied": tie_break_applied,
        "tie_break_reason": tie_break_reason,
        "decision_reason": (
            "highest_validated_confidence"
            if not tie_break_applied
            else f"tie_break:{tie_break_reason}"
        ),
        "alternatives": [
            {
                "source": c.get("source"),
                "value": c.get("value"),
                "confidence": float(c.get("confidence", 0.0)),
                "validated": bool(c.get("validated")),
                "losing_reason": (
                    "not_selected_after_tie_break"
                    if tie_break_applied
                    else "lower_confidence_or_invalid"
                ),
            }
            for c in candidates
            if c is not chosen
        ],
    }
    return chosen_value, decision


def resolve_all_fields(
    candidate_map: dict[str, list[dict[str, Any]]],
    current_lead: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved = dict(current_lead)
    decisions: dict[str, Any] = {}

    for field in TRACKED_FIELDS:
        value, decision = resolve_field_candidates(
            field,
            candidate_map.get(field, []),
            current_value=current_lead.get(field),
            current_source="current",
        )
        resolved[field] = value
        decisions[field] = decision

    return resolved, decisions

