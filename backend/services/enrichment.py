def enrich_lead(lead: dict) -> dict:
    """Placeholder multi-source enrichment."""
    enriched = dict(lead)
    enriched.setdefault("source", "input")
    return enriched
