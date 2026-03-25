from backend.core.normalizer import (
    normalize_company_name_for_dedupe,
    normalize_email,
    normalize_phone,
    normalize_website,
)


def deduplicate(leads: list[dict]) -> list[dict]:
    """
    Deduplicate with a clear precedence order:
    1) normalized `website`
    2) normalized `company_name`
    3) normalized contact (`email` or `phone`)
    """
    seen: set[tuple[str, str]] = set()
    output: list[dict] = []

    for lead in leads:
        website = normalize_website(lead.get("website"))
        company = lead.get("company_name")
        company_norm = normalize_company_name_for_dedupe(company)

        email = normalize_email(lead.get("email"))
        phone = normalize_phone(lead.get("phone"))
        contact_norm = email or phone

        if website:
            key = ("website", website)
        elif company_norm:
            key = ("company", company_norm)
        elif contact_norm:
            key = ("contact", contact_norm)
        else:
            # Identity-less leads should have been filtered earlier.
            key = ("unknown", "unknown")

        if key in seen:
            continue
        seen.add(key)
        output.append(lead)

    return output
