def normalize_lead(lead: dict) -> dict:
    normalized = dict(lead)
    for key in ("company_name", "agent_name", "website", "email", "phone", "location"):
        if key in normalized and isinstance(normalized[key], str):
            normalized[key] = normalized[key].strip()
    return normalized
