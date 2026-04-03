from __future__ import annotations

from typing import Any

from backend.services.contact_parser import normalize_email_advanced, normalize_phone_advanced


def compute_contact_quality(
    email: str | None,
    phone: str | None,
    *,
    default_phone_region: str = "ZA",
) -> tuple[str, dict[str, Any]]:
    """
    Derive contact_quality from the same rules as contact extraction (contact_parser).
    Both valid -> verified; one valid -> likely; else low.
    """
    email_raw = str(email).strip() if email else ""
    phone_raw = str(phone).strip() if phone else ""

    email_parsed = normalize_email_advanced(email_raw if email_raw else None)
    phone_parsed = normalize_phone_advanced(phone_raw if phone_raw else None, default_region=default_phone_region)

    email_ok = bool(email_parsed.get("valid") and email_parsed.get("value"))
    phone_ok = bool(phone_parsed.get("valid") and phone_parsed.get("value"))

    if email_ok and phone_ok:
        quality = "verified"
    elif email_ok or phone_ok:
        quality = "likely"
    else:
        quality = "low"

    verification: dict[str, Any] = {
        "email": {
            "valid": email_ok,
            "normalized": email_parsed.get("value"),
            "reason": email_parsed.get("reason"),
            "is_disposable": bool(email_parsed.get("is_disposable")),
        },
        "phone": {
            "valid": phone_ok,
            "normalized": phone_parsed.get("value"),
            "reason": phone_parsed.get("reason"),
        },
    }
    return quality, verification


def verify_lead(lead: dict[str, Any], *, in_place: bool = False, default_phone_region: str = "ZA") -> dict[str, Any]:
    """Set contact_quality and verification on a lead using contact_parser rules."""
    target = lead if in_place else dict(lead)
    quality, verification = compute_contact_quality(
        target.get("email"),
        target.get("phone"),
        default_phone_region=default_phone_region,
    )
    target["contact_quality"] = quality
    target["verification"] = verification
    return target
