"""
Request/response schemas for feature/auth.
"""
import re
import uuid
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

_KE_PHONE = re.compile(r"^(?:\+?254|0)([17]\d{8})$")


# --- Onboarding (FR1.1-1.3) ---

class MemberOnboardRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_minor: bool = False
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    id_number: Optional[str] = Field(default=None, pattern=r"^\d{8}$")
    category: Optional[str] = Field(default=None, max_length=50)
    household_id: Optional[uuid.UUID] = None 

    @field_validator(
        "name", "phone_number", "email", "id_number", "category", "household_id",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, v):
        """Trim whitespace and treat empty strings as 'not provided'."""
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("phone_number")
    @classmethod
    def normalize_phone(cls, v):
        """Accept 07XX.., 01XX.., 2547XX.. or +2547XX.. and store as +254XXXXXXXXX."""
        if v is None:
            return v
        cleaned = re.sub(r"[\s\-()]", "", v)
        match = _KE_PHONE.match(cleaned)
        if not match:
            raise ValueError(
                "Phone number must be a valid Kenyan number, e.g. 0712345678 or +254712345678"
            )
        return f"+254{match.group(1)}"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v):
        """Lowercase so Mary@x.com and mary@x.com can't both pass the unique check."""
        if v is None:
            return v
        v = v.lower()
        if len(v) > 50:
            raise ValueError("Email must be 50 characters or fewer")
        return v

    @model_validator(mode="after")
    def adult_needs_contact_info(self):
        """
        FR1.3 requires the system to deliver a temp password via send_sms()
        immediately on creation. An adult member with neither phone nor
        email has nowhere for that credential to go, so this blocks the
        request before it ever reaches auth_service.onboard_member().

        Minors are exempt: per FR1.7, phone/email are intentionally left
        null for them; they never receive login credentials at all.
        """
        if not self.is_minor and not self.phone_number and not self.email:
            raise ValueError(
                "An adult member needs at least a phone or an email, "
                "otherwise there's no way to deliver their login credentials."
            )
        return self


class MemberOnboardResponse(BaseModel):
    id: str
    name: str
    is_minor: bool
    phone_number: Optional[str] = None
    email: Optional[str] = None
    temp_password_sent: bool
    # Deliberately no password field: never echo credential material back,
    # even the temporary one.


# --- Login (FR1.4-1.5) ---
# The router uses OAuth2PasswordRequestForm for the request, so there is
# no LoginRequest schema any more. Only the response is defined here.

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # Lets the client route straight to the change-password screen
    # without decoding the JWT.
    must_change_password: bool
    member_id: str
    name: str


# --- Change password (FR1.4) ---

class ChangePasswordRequest(BaseModel):
    current_password: str
    # max_length=72 because bcrypt ignores everything past 72 bytes
    new_password: str = Field(min_length=8, max_length=72)

    @model_validator(mode="after")
    def must_differ(self):
        if self.new_password == self.current_password:
            raise ValueError("New password must be different from the current password")
        return self


class ChangePasswordResponse(BaseModel):
    detail: str = "Password changed successfully. Please log in again."