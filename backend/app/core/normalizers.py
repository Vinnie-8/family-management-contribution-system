"""
Normalisation of phone numbers, emails and login identifiers, so the same
person always matches the same stored value (and the unique columns work).
Pure functions: used by schemas, services and scripts alike.
"""
import re
from typing import Optional

_KE_PHONE = re.compile(r"^(?:\+?254|0)([17]\d{8})$")


def normalize_phone(raw: str) -> Optional[str]:
    """07XX.., 01XX.., 2547XX.. or +2547XX.. -> +254XXXXXXXXX. None if not a valid Kenyan number."""
    cleaned = re.sub(r"[\s\-()]", "", raw.strip())
    match = _KE_PHONE.match(cleaned)
    return f"+254{match.group(1)}" if match else None


def normalize_email(raw: str) -> str:
    """Lowercase, so Mary@x.com and mary@x.com can't both pass the unique check."""
    return raw.strip().lower()


def normalize_identifier(identifier: str) -> str:
    """A login identifier is either an email or a phone number."""
    identifier = identifier.strip()
    if "@" in identifier:
        return normalize_email(identifier)
    return normalize_phone(identifier) or identifier