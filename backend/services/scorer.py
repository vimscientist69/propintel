def score_lead(lead: dict) -> tuple[int, str]:
    """Starter scoring heuristic for MVP bootstrapping."""
    score = 50
    reasons: list[str] = []

    if not lead.get("has_chatbot"):
        score += 15
        reasons.append("No chatbot")
    if not lead.get("email") and not lead.get("phone"):
        score += 20
        reasons.append("Missing contact info")

    score = max(0, min(100, score))
    reason = ", ".join(reasons) if reasons else "Baseline score"
    return score, reason
