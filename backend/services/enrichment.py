from __future__ import annotations

import os
from typing import Any

from backend.services.contact_parser import normalize_email_advanced, normalize_phone_advanced
from backend.services.scraper import (
    discover_contact_page_urls,
    detect_chatbot_signal,
    detect_freshness_signal,
    discover_company_website,
    extract_contacts_from_jsonld,
    extract_contacts_from_html,
    fetch_website_html,
    latency_to_speed_score,
)


def _load_env() -> None:
    # Allow .env-based local usage without requiring shell export.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def _pick_first(values: list[str]) -> str | None:
    return values[0] if values else None


def _fetch_with_retries(
    website: str,
    *,
    timeout_seconds: int,
    user_agent: str,
    max_retries: int,
) -> dict[str, Any]:
    attempts = max(0, max_retries) + 1
    last_result: dict[str, Any] = {"ok": False, "html": "", "error": "unknown"}
    for _ in range(attempts):
        last_result = fetch_website_html(
            website,
            timeout_seconds=timeout_seconds,
            user_agent=user_agent,
        )
        if last_result.get("ok"):
            return last_result
    return last_result


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
    max_retries = int(cfg.get("max_retries", 2))
    user_agent = str(cfg.get("user_agent", "PropIntelBot/0.1"))
    chatbot_keywords = cfg.get("chatbot_keywords") or []

    website = (enriched.get("website") or "").strip()
    if not website and cfg.get("discover_with_serper", True):
        company_name = str(enriched.get("company_name") or "").strip()
        location = str(enriched.get("location") or "").strip() or None
        discovered = discover_company_website(
            company_name=company_name,
            serper_api_key=os.getenv("SERPER_API_KEY"),
            timeout_seconds=serper_timeout_seconds,
        )
        if discovered:
            website = discovered
            enriched["website"] = discovered

    # If no website could be found, skip website enrichment gracefully.
    # contact_quality is set once after conflict resolution in ingestion (verify_lead).
    if not website:
        return enriched

    fetch_result = _fetch_with_retries(
        website,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
        max_retries=max_retries,
    )
    if not fetch_result.get("ok"):
        if cfg.get("discover_with_serper", True):
            company_name = str(enriched.get("company_name") or "").strip()
            discovered = discover_company_website(
                company_name=company_name,
                serper_api_key=os.getenv("SERPER_API_KEY"),
                timeout_seconds=serper_timeout_seconds,
            )
            if discovered and discovered != website:
                enriched["website"] = discovered
                website = discovered
                fetch_result = _fetch_with_retries(
                    website,
                    timeout_seconds=timeout_seconds,
                    user_agent=user_agent,
                    max_retries=max_retries,
                )

        # If retries failed and discovery is disabled or unsuccessful, null website.
        if not fetch_result.get("ok"):
            if not cfg.get("discover_with_serper", True) or not enriched.get("website"):
                enriched["website"] = None
            enriched["enrichment_error"] = fetch_result.get("error")
            return enriched

    if not fetch_result.get("ok"):
        enriched["enrichment_error"] = fetch_result.get("error")
        return enriched

    html = str(fetch_result.get("html") or "")
    page_htmls: list[tuple[str, str]] = [(website, html)]
    extra_pages = discover_contact_page_urls(website, html)
    multi_page_fetch_success = 0
    for page_url in extra_pages:
        page_result = fetch_website_html(
            page_url,
            timeout_seconds=timeout_seconds,
            user_agent=user_agent,
        )
        if page_result.get("ok"):
            multi_page_fetch_success += 1
            page_htmls.append((page_url, str(page_result.get("html") or "")))

    all_emails: list[str] = []
    all_phones: list[str] = []
    schema_contacts_used = 0
    for _, page_html in page_htmls:
        regular = extract_contacts_from_html(page_html)
        schema = extract_contacts_from_jsonld(page_html)
        if schema.get("emails") or schema.get("phones"):
            schema_contacts_used += 1
        all_emails.extend(schema.get("emails", []))
        all_emails.extend(regular.get("emails", []))
        all_phones.extend(schema.get("phones", []))
        all_phones.extend(regular.get("phones", []))

    email_disposable_rejected = 0
    selected_email: str | None = None
    selected_email_reason = "none"
    selected_email_quality = "low"
    for candidate_email in all_emails:
        parsed = normalize_email_advanced(candidate_email)
        if parsed.get("is_disposable"):
            email_disposable_rejected += 1
        if parsed.get("valid") and parsed.get("value"):
            selected_email = str(parsed["value"])
            selected_email_reason = str(parsed.get("reason") or "valid_email")
            selected_email_quality = str(parsed.get("quality") or "medium")
            break

    selected_phone: str | None = None
    selected_phone_reason = "none"
    phone_valid_count = 0
    for candidate_phone in all_phones:
        parsed = normalize_phone_advanced(candidate_phone)
        if parsed.get("valid") and parsed.get("value"):
            phone_valid_count += 1
            if selected_phone is None:
                selected_phone = str(parsed["value"])
                selected_phone_reason = str(parsed.get("reason") or "valid_phone")

    if not enriched.get("email") and selected_email:
        enriched["email"] = selected_email
    if not enriched.get("phone") and selected_phone:
        enriched["phone"] = selected_phone

    enriched["_website_values"] = {
        "email": selected_email,
        "phone": selected_phone,
    }
    combined_html = "\n".join(page_html for _, page_html in page_htmls)
    primary_elapsed = fetch_result.get("elapsed_ms")
    speed_score = latency_to_speed_score(primary_elapsed if isinstance(primary_elapsed, int) else None)

    enriched["_website_contact_stats"] = {
        "schema_contacts_used": schema_contacts_used,
        "email_disposable_rejected": email_disposable_rejected,
        "multi_page_fetch_success": multi_page_fetch_success,
        "phone_valid_count": phone_valid_count,
        "phone_total_candidates": len(all_phones),
        "email_validation_reason": selected_email_reason,
        "phone_validation_reason": selected_phone_reason,
        "email_quality": selected_email_quality,
        "fetch_elapsed_ms": primary_elapsed,
    }

    enriched["has_chatbot"] = detect_chatbot_signal(combined_html, chatbot_keywords)
    enriched["last_updated_signal"] = "detected" if detect_freshness_signal(combined_html) else "unknown"
    if speed_score is not None:
        enriched["website_speed_score"] = speed_score
    return enriched