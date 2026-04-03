from __future__ import annotations

from typing import Any


def _w(cfg: dict[str, Any], key: str, default: float = 0.0) -> float:
    weights = cfg.get("weights") if isinstance(cfg.get("weights"), dict) else {}
    return float(weights.get(key, default))


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def score_lead(lead: dict[str, Any], scoring_cfg: dict[str, Any] | None = None) -> tuple[int, str]:
    """
    Deterministic lead score 0–100 and human-readable reason string.
    Uses contact_quality / verification (no duplicate disposable checks).
    """
    cfg = scoring_cfg if isinstance(scoring_cfg, dict) else {}
    base = int(cfg.get("base_score", 45))
    score = float(base)
    fragments: list[str] = []

    # --- Dimension 3: contact strength ---
    cq = str(lead.get("contact_quality") or "").strip().lower()
    if cq == "verified":
        score += _w(cfg, "contact_quality_verified", 25)
        fragments.append("Contact quality verified")
    elif cq == "likely":
        score += _w(cfg, "contact_quality_likely", 10)
        fragments.append("Contact quality likely")
    elif cq == "low":
        score += _w(cfg, "contact_quality_low", -15)
        fragments.append("Contact quality low")
    else:
        fragments.append("Contact quality unknown")

    ver = lead.get("verification") if isinstance(lead.get("verification"), dict) else {}
    em = ver.get("email") if isinstance(ver.get("email"), dict) else {}
    ph = ver.get("phone") if isinstance(ver.get("phone"), dict) else {}
    em_ok = bool(em.get("valid"))
    ph_ok = bool(ph.get("valid"))
    if em_ok and ph_ok and cq == "likely":
        score += _w(cfg, "both_channels_bonus", 5)
        fragments.append("Both email and phone valid")

    # --- Website presence ---
    if _non_empty_str(lead.get("website")):
        score += _w(cfg, "has_website", 10)
        fragments.append("Website on record")

    # --- Dimension 1: chatbot / automation ---
    hb = lead.get("has_chatbot")
    if hb is True:
        score += _w(cfg, "chatbot_penalty", -10)
        fragments.append("Chatbot or live-widget signal on site")
    elif hb is False:
        fragments.append("No chatbot-style widgets detected")
    else:
        fragments.append("Chatbot status unknown (no site crawl)")

    # --- Dimension 2: freshness / outdated ---
    lu = str(lead.get("last_updated_signal") or "").strip().lower()
    if lu == "detected":
        score += _w(cfg, "last_updated_bonus", 5)
        fragments.append("Freshness wording on page")
    else:
        score += _w(cfg, "last_updated_unknown_penalty", 0)
        if lu == "unknown" or not lu:
            fragments.append("No freshness signal in crawl")
    ws = lead.get("website_speed_score")
    if ws is not None and ws != "":
        fragments.append("Website speed score present")

    # --- Dimension 4: business activity ---
    src = str(lead.get("source") or "").lower()
    if "google_maps" in src:
        score += _w(cfg, "google_maps_source_bonus", 5)
        fragments.append("Google Maps enrichment")
    if _non_empty_str(lead.get("location")):
        score += _w(cfg, "has_location_bonus", 3)
        fragments.append("Location on record")
    if _non_empty_str(lead.get("agent_name")):
        score += _w(cfg, "has_agent_name_bonus", 2)
        fragments.append("Agent name on record")

    final = int(round(max(0.0, min(100.0, score))))
    # Keep reason readable: join first N fragments (enough for all dimensions)
    reason_parts = fragments[:8]
    reason = "; ".join(reason_parts) if reason_parts else "Baseline score"
    return final, reason


def confidence_from_score(lead_score: int) -> int:
    """MVP: map score to confidence_score 0–100 (same scale)."""
    return max(0, min(100, int(lead_score)))
