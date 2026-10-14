def normalize_email(email: str) -> str:
    """Return the canonical form used for email identity comparisons."""
    return email.strip().lower()
