from __future__ import annotations

import re
from typing import Any


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "10minutemail.com",
    "guerrillamail.com",
    "tempmail.com",
    "yopmail.com",
}
ROLE_PREFIXES = {"info", "support", "admin", "sales", "contact"}


def normalize_phone_advanced(
    phone: str | None,
    *,
    default_region: str = "ZA",
) -> dict[str, Any]:
    raw = str(phone or "").strip()
    if not raw:
        return {"value": None, "valid": False, "reason": "empty_phone", "raw": raw}

    try:
        import phonenumbers

        parsed = phonenumbers.parse(raw, default_region)
        if not phonenumbers.is_valid_number(parsed):
            return {"value": None, "valid": False, "reason": "invalid_number", "raw": raw}
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return {"value": e164, "valid": True, "reason": "valid_e164", "raw": raw}
    except Exception:
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 7:
            return {"value": None, "valid": False, "reason": "invalid_digits", "raw": raw}
        normalized = f"+{digits}" if raw.startswith("+") else digits
        return {"value": normalized, "valid": True, "reason": "fallback_normalized", "raw": raw}


def normalize_email_advanced(email: str | None) -> dict[str, Any]:
    raw = str(email or "").strip().lower()
    if not raw:
        return {
            "value": None,
            "valid": False,
            "reason": "empty_email",
            "is_disposable": False,
            "quality": "low",
            "is_role_based": False,
        }
    if not EMAIL_RE.match(raw):
        return {
            "value": None,
            "valid": False,
            "reason": "invalid_format",
            "is_disposable": False,
            "quality": "low",
            "is_role_based": False,
        }
    local, _, domain = raw.partition("@")
    is_disposable = domain in DISPOSABLE_DOMAINS
    is_role_based = local in ROLE_PREFIXES
    if is_disposable:
        return {
            "value": None,
            "valid": False,
            "reason": "disposable_domain",
            "is_disposable": True,
            "quality": "low",
            "is_role_based": is_role_based,
        }
    quality = "medium" if is_role_based else "high"
    return {
        "value": raw,
        "valid": True,
        "reason": "valid_email",
        "is_disposable": False,
        "quality": quality,
        "is_role_based": is_role_based,
    }

