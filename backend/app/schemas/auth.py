"""
Request/response schemas for feature/auth.
Member onboarding schemas live in schemas/members.py.
"""
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ContactFields, NewPassword, empty_to_none


# --- Register a family (Chairman) ---

class RegisterFamilyRequest(ContactFields):
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
        return empty_to_none(v)

    @model_validator(mode="after")
    def needs_contact(self):
        # A member with a password must have a phone or email (database rule).
        if not self.phone_number and not self.email:
            raise ValueError("A phone number or an email is required")
        return self


# --- Activate (first password, from the invite link) ---

class ActivateRequest(ContactFields):
    token: str = Field(min_length=1)
    new_password: NewPassword
    # Phone/email are only needed by a minor who has just come of age and has no contact of their own yet.


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