def deduplicate(leads: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    output: list[dict] = []

    for lead in leads:
        key = (
            str(lead.get("website", "")).lower(),
            str(lead.get("company_name", "")).lower(),
            str(lead.get("email", "")).lower() or str(lead.get("phone", "")).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(lead)

    return output
