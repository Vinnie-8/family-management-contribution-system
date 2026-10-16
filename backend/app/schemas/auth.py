"""
Request/response schemas for feature/auth.
Member onboarding schemas live with feature/members.
"""
from typing import Annotated, Optional

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.core.normalizers import normalize_email, normalize_phone

_BCRYPT_MAX_BYTES = 72


def _empty_to_none(v):
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


class _ContactFields(BaseModel):
    """Optional phone and email, cleaned the same way everywhere."""
    model_config = ConfigDict(str_strip_whitespace=True)

    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None

    @field_validator("phone_number", "email", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return _empty_to_none(v)

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


# --- Register a family (Chairman) ---

class RegisterFamilyRequest(_ContactFields):
    registration_code: str = Field(min_length=1, max_length=50)
    family_name: str = Field(min_length=1, max_length=100)
    # Each family chooses its own minor age limit; 18 unless they say otherwise.
    age_of_majority: int = Field(default=18, ge=1, le=30)
    name: str = Field(min_length=1, max_length=100)
    id_number: Optional[str] = Field(default=None, pattern=r"^\d{8}$")
    password: NewPassword

    @field_validator("id_number", mode="before")
    @classmethod
    def id_blank_to_none(cls, v):
        return _empty_to_none(v)

    @model_validator(mode="after")
    def needs_contact(self):
        # A member with a password must have a phone or email (database rule).
        if not self.phone_number and not self.email:
            raise ValueError("A phone number or an email is required")
        return self


# --- Activate (first password, from the invite link) ---

class ActivateRequest(_ContactFields):
    token: str = Field(min_length=1)
    new_password: NewPassword
    # Only needed by a minor who has just come of age and has no contact of their own yet.


# --- Login ---
# The router uses OAuth2PasswordRequestForm for the request, so there is
# no LoginRequest schema. Only the response is defined here.

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    member_id: str
    name: str


# --- Change password ---

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: NewPassword

    @model_validator(mode="after")
    def must_differ(self):
        if self.new_password == self.current_password:
            raise ValueError("New password must be different from the current password")
        return self


class ChangePasswordResponse(BaseModel):
    detail: str = "Password changed successfully."