def verify_contact_quality(email: str | None, phone: str | None) -> str:
    """Basic starter contact-quality decision."""
    if email and phone:
        return "verified"
    if email or phone:
        return "likely"
    return "low"
