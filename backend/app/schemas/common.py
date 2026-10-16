"""
Building blocks shared by the auth and members schemas: cleaning of phone,
email and password input, so every endpoint treats them the same way.
"""
import re
from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.normalizers import normalize_email, normalize_phone

_BCRYPT_MAX_BYTES = 72
_EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def empty_to_none(v):
    """Trim whitespace and treat empty strings as 'not provided'."""
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _check_password_bytes(v: str) -> str:
    # bcrypt reads 72 BYTES, and one accented or non-Latin character can be several.
    if len(v.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        raise ValueError("Password is too long (72 bytes at most)")
    return v


NewPassword = Annotated[str, Field(min_length=8), AfterValidator(_check_password_bytes)]


def normalize_contact(v: str) -> str:
    """A phone number or an email, cleaned the way it is stored. Raises ValueError if neither."""
    v = v.strip()
    if "@" in v:
        email = normalize_email(v)
        if not _EMAIL_SHAPE.match(email) or len(email) > 50:
            raise ValueError("Enter a valid email of 50 characters or fewer")
        return email
    phone = normalize_phone(v)
    if phone is None:
        raise ValueError("Enter a valid Kenyan phone number or an email")
    return phone


class ContactFields(BaseModel):
    """Optional phone and email, cleaned the same way everywhere."""
    model_config = ConfigDict(str_strip_whitespace=True)

    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None

    @field_validator("phone_number", "email", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return empty_to_none(v)

    @field_validator("phone_number")
    @classmethod
    def phone_format(cls, v):
        if v is None:
            return v
        normalized = normalize_phone(v)
        if normalized is None:
            raise ValueError("Phone number must be a valid Kenyan number, e.g. 0712345678 or +254712345678")
        return normalized

    @field_validator("email")
    @classmethod
    def email_format(cls, v):
        if v is None:
            return v
        v = normalize_email(v)
        if len(v) > 50:
            raise ValueError("Email must be 50 characters or fewer")
        return v