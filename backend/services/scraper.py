from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.parse import urljoin, urlparse

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\+?\d[\d\-\s()]{6,}\d")


def _normalize_url(url: str) -> str | None:
    raw = (url or "").strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    return raw


def fetch_website_html(
    url: str,
    *,
    timeout_seconds: int = 8,
    user_agent: str = "PropIntelBot/0.1",
) -> dict[str, Any]:
    import requests

    normalized = _normalize_url(url)
    if not normalized:
        return {
            "ok": False,
            "url": None,
            "status_code": None,
            "html": "",
            "error": "empty_url",
            "elapsed_ms": None,
        }

    try:
        t0 = time.perf_counter()
        response = requests.get(
            normalized,
            timeout=timeout_seconds,
            headers={"User-Agent": user_agent},
        )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "ok": response.ok,
            "url": normalized,
            "status_code": response.status_code,
            "html": response.text if response.ok else "",
            "error": None if response.ok else f"http_{response.status_code}",
            "elapsed_ms": elapsed_ms,
        }
    except requests.RequestException as exc:
        try:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)  # type: ignore[name-defined]
        except Exception:
            elapsed_ms = None
        return {
            "ok": False,
            "url": normalized,
            "status_code": None,
            "html": "",
            "error": str(exc),
            "elapsed_ms": elapsed_ms,
        }


def extract_contacts_from_html(html: str) -> dict[str, list[str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text(" ", strip=True)

    emails = set(EMAIL_RE.findall(text))
    phones = set(PHONE_RE.findall(text))

    # Add explicit mailto/tel links when present.
    for tag in soup.select("a[href]"):
        href = (tag.get("href") or "").strip()
        if href.startswith("mailto:"):
            email = href.replace("mailto:", "", 1).split("?")[0].strip()
            if email:
                emails.add(email)
        elif href.startswith("tel:"):
            phone = href.replace("tel:", "", 1).strip()
            if phone:
                phones.add(phone)

    return {
        "emails": sorted(emails),
        "phones": sorted(phones),
    }


# Third-party chat / automation scripts (substring match on full HTML).
CHATBOT_VENDOR_PATTERNS: tuple[str, ...] = (
    "intercom.io",
    "intercom-",
    "drift.com",
    "driftt.com",
    "js.hs-scripts.com",
    "hubspotfeedback",
    "usemessages.com/conversations-embed",
    "tawk.to",
    "embed.tawk.to",
    "crisp.chat",
    "client.crisp.chat",
    "livechatinc.com",
    "cdn.livechatinc.com",
    "zendesk.com/embeddable",
    "static.zdassets.com",
    "olark.com",
    "snapengage.com",
    "tidiochat",
    "tidio.co",
    "purechat.com",
    "facebook.com/platform/chat",
    "whatsapp.com/send",
    "smartsuppchat",
    "userlike.com",
)


def detect_chatbot_signal(html: str, chatbot_keywords: list[str] | None = None) -> bool:
    """
    True if configured keywords appear in HTML or common chat-widget vendor URLs/scripts match.
    """
    keywords = chatbot_keywords or []
    haystack = (html or "").lower()
    if any(keyword.lower() in haystack for keyword in keywords):
        return True
    return any(pat in haystack for pat in CHATBOT_VENDOR_PATTERNS)


_FRESHNESS_PATTERNS = (
    re.compile(r"last\s+(updated|modified|revised|edited)", re.I),
    re.compile(r"updated\s*:", re.I),
    re.compile(r"article:modified_time", re.I),
    re.compile(r"og:updated_time", re.I),
    re.compile(r"datepublished|datemodified", re.I),
    re.compile(r"<time[^>]+datetime=", re.I),
)


def detect_freshness_signal(html: str) -> bool:
    """
    Heuristic: page suggests recent maintenance (wording, meta, structured data).
    """
    if not (html or "").strip():
        return False
    low = html.lower()
    if "updated" in low and len(low) > 200:
        return True
    for rx in _FRESHNESS_PATTERNS:
        if rx.search(html):
            return True
    return False


def latency_to_speed_score(elapsed_ms: int | None) -> int | None:
    """
    Map HTTP fetch duration to 0–100 (higher = snappier). None if no measurement.
    """
    if elapsed_ms is None or elapsed_ms < 0:
        return None
    if elapsed_ms < 400:
        return 100
    if elapsed_ms < 900:
        return 88
    if elapsed_ms < 1800:
        return 72
    if elapsed_ms < 3500:
        return 55
    if elapsed_ms < 6000:
        return 35
    return max(5, 25 - min(20, (elapsed_ms - 6000) // 500))


def extract_contacts_from_jsonld(html: str) -> dict[str, list[str]]:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return {"emails": [], "phones": []}

    soup = BeautifulSoup(html or "", "html.parser")
    emails: set[str] = set()
    phones: set[str] = set()
    for tag in soup.select("script[type='application/ld+json']"):
        raw = (tag.string or tag.get_text() or "").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            email = str(item.get("email") or "").strip()
            phone = str(item.get("telephone") or "").strip()
            if email:
                emails.add(email)
            if phone:
                phones.add(phone)
            contact_point = item.get("contactPoint")
            cp_items = contact_point if isinstance(contact_point, list) else [contact_point]
            for cp in cp_items:
                if not isinstance(cp, dict):
                    continue
                cp_email = str(cp.get("email") or "").strip()
                cp_phone = str(cp.get("telephone") or "").strip()
                if cp_email:
                    emails.add(cp_email)
                if cp_phone:
                    phones.add(cp_phone)
    return {"emails": sorted(emails), "phones": sorted(phones)}


def discover_contact_page_urls(base_url: str, html: str) -> list[str]:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return []

    soup = BeautifulSoup(html or "", "html.parser")
    discovered: list[str] = []
    seen: set[str] = set()
    keywords = ("contact", "about", "team", "agents")
    for tag in soup.select("a[href]"):
        href = (tag.get("href") or "").strip()
        if not href:
            continue
        low = href.lower()
        if not any(k in low for k in keywords):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        discovered.append(absolute)
    return discovered[:3]


def _is_plausible_company_domain(company_name: str, candidate_url: str) -> bool:
    parsed = urlparse(candidate_url)
    host = parsed.netloc.lower()
    if not host:
        return False

    blocked = ("facebook.com", "instagram.com", "linkedin.com", "x.com", "twitter.com")
    if any(blocked_host in host for blocked_host in blocked):
        return False

    # Basic token overlap with company name.
    tokens = [t for t in re.split(r"[^a-z0-9]+", company_name.lower()) if len(t) > 2]
    host_compact = re.sub(r"[^a-z0-9]", "", host)
    if not tokens:
        return True

    # 1) Direct token overlap (existing behavior).
    if any(token in host for token in tokens):
        return True

    # 2) Acronym/abbreviation overlap for short-brand domains.
    # Example: "Southern Cape Properties" -> "scp" / "scprop" should match scprop.co.za.
    initials = "".join(token[0] for token in tokens if token)
    if len(initials) >= 2 and initials in host_compact:
        return True

    # 3) Real-estate shorthand where "properties/property" is often shortened to "prop".
    has_property_word = any(token in ("property", "properties") for token in tokens)
    non_property_tokens = [t for t in tokens if t not in ("property", "properties")]
    if has_property_word and non_property_tokens:
        shorthand = "".join(token[0] for token in non_property_tokens) + "prop"
        if shorthand in host_compact:
            return True

    return False


def discover_company_website(
    *,
    company_name: str,
    serper_api_key: str | None,
    timeout_seconds: int = 6,
) -> str | None:
    import requests

    if not company_name or not serper_api_key:
        return None

    query = f"{company_name} official website"

    try:
        response = requests.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": serper_api_key,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": 5},
            timeout=timeout_seconds,
        )
        if not response.ok:
            return None

        payload = response.json()
        for item in payload.get("organic", []) or []:
            candidate = _normalize_url(str(item.get("link") or ""))
            if candidate and _is_plausible_company_domain(company_name, candidate):
                return candidate
    except requests.RequestException:
        return None
    except ValueError:
        return None

    return None
