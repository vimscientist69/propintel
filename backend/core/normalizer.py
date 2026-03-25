import re
from typing import Any


def normalize_website(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    if not v:
        return None

    # Remove scheme for consistent dedup keys.
    v = re.sub(r"^https?://", "", v)
    v = v.lstrip("www.")
    v = v.rstrip("/")
    return v or None


def normalize_email(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    return v or None


def normalize_phone(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None

    has_plus = v.startswith("+")
    digits = re.sub(r"\D", "", v)
    if not digits:
        return None

    return f"+{digits}" if has_plus else digits


def normalize_company_name_for_dedupe(value: Any) -> str | None:
    """
    Normalize company names for deduplication keys.

    Output is lowercased to make dedup stable regardless of input casing.
    """
    if not isinstance(value, str):
        return None
    v = re.sub(r"\s+", " ", value.strip())
    if not v:
        return None
    return v.lower()


def normalize_lead(lead: dict) -> dict:
    normalized = dict(lead)

    # Identity / names
    for key in ("company_name", "agent_name", "location"):
        if key in normalized and isinstance(normalized[key], str):
            normalized[key] = re.sub(r"\s+", " ", normalized[key].strip())

    # Contacts / website
    if "website" in normalized:
        normalized["website"] = normalize_website(normalized.get("website"))
    if "email" in normalized:
        normalized["email"] = normalize_email(normalized.get("email"))
    if "phone" in normalized:
        normalized["phone"] = normalize_phone(normalized.get("phone"))

    return normalized
