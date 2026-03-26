from __future__ import annotations

import os
import re
from typing import Any

from backend.services.scraper import (
    detect_chatbot_signal,
    discover_company_website,
    extract_contacts_from_html,
    fetch_website_html,
)
from backend.services.verifier import verify_contact_quality


def _load_env() -> None:
    # Allow .env-based local usage without requiring shell export.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def _pick_first(values: list[str]) -> str | None:
    return values[0] if values else None


def _normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None
    return f"+{digits}" if phone.strip().startswith("+") else digits


def enrich_lead(
    lead: dict[str, Any],
    website_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = dict(lead)
    enriched.setdefault("source", "input")

    cfg = website_config or {}
    if not cfg.get("enabled", True):
        return enriched

    _load_env()

    timeout_seconds = int(cfg.get("request_timeout_seconds", 8))
    serper_timeout_seconds = int(cfg.get("serper_timeout_seconds", 6))
    user_agent = str(cfg.get("user_agent", "PropIntelBot/0.1"))
    chatbot_keywords = cfg.get("chatbot_keywords") or []

    website = (enriched.get("website") or "").strip()
    if not website and cfg.get("discover_with_serper", True):
        company_name = str(enriched.get("company_name") or "").strip()
        location = str(enriched.get("location") or "").strip() or None
        discovered = discover_company_website(
            company_name=company_name,
            location=location,
            serper_api_key=os.getenv("SERPER_API_KEY"),
            timeout_seconds=serper_timeout_seconds,
        )
        if discovered:
            website = discovered
            enriched["website"] = discovered

    # If no website could be found, skip website enrichment gracefully.
    if not website:
        enriched["contact_quality"] = verify_contact_quality(
            enriched.get("email"),
            enriched.get("phone"),
        )
        return enriched

    fetch_result = fetch_website_html(
        website,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
    )
    if not fetch_result.get("ok"):
        enriched["contact_quality"] = verify_contact_quality(
            enriched.get("email"),
            enriched.get("phone"),
        )
        enriched["enrichment_error"] = fetch_result.get("error")
        return enriched

    html = str(fetch_result.get("html") or "")
    contacts = extract_contacts_from_html(html)
    scraped_email = _pick_first(contacts.get("emails", []))
    scraped_phone = _normalize_phone(_pick_first(contacts.get("phones", [])))

    if not enriched.get("email") and scraped_email:
        enriched["email"] = scraped_email
    if not enriched.get("phone") and scraped_phone:
        enriched["phone"] = scraped_phone

    enriched["has_chatbot"] = detect_chatbot_signal(html, chatbot_keywords)
    enriched["last_updated_signal"] = "detected" if "updated" in html.lower() else "unknown"
    enriched["contact_quality"] = verify_contact_quality(
        enriched.get("email"),
        enriched.get("phone"),
    )
    return enriched
