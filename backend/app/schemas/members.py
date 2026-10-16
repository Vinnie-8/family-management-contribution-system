"""
Request/response schemas for feature/members.

Privacy: no member response ever contains a date of birth. Lists show only
"adult" or "minor". The one exception is the audited lookup endpoint.
"""
import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ContactFields, empty_to_none, normalize_contact


# --- Onboarding ---

class MemberOnboardRequest(ContactFields):
    # The Chairman or Secretary states which kind of member this is.
    member_type: Literal["adult", "minor"] = "adult"
    name: str = Field(min_length=1, max_length=100)
    id_number: Optional[str] = Field(default=None, pattern=r"^\d{8}$")
    category: Optional[str] = Field(default=None, max_length=50)
    # Required for an adult. A minor can leave it out and join their guardian's household.
    household_id: Optional[uuid.UUID] = None

    # Minors only
    date_of_birth: Optional[date] = None
    guardian_member_id: Optional[uuid.UUID] = None
    relationship_label: Optional[str] = Field(default=None, max_length=50)
    # Parent/guardian phone or email, used to send the activation link when the minor comes of age.
    invite_contact: Optional[str] = None

    @field_validator(
        "id_number", "category", "household_id", "date_of_birth",
        "guardian_member_id", "relationship_label", "invite_contact",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, v):
        return empty_to_none(v)

    @field_validator("date_of_birth")
    @classmethod
    def not_in_future(cls, v):
        if v is not None and v > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return v

    @field_validator("invite_contact")
    @classmethod
    def clean_invite_contact(cls, v):
        return None if v is None else normalize_contact(v)

    @model_validator(mode="after")
    def check_rules_for_member_type(self):
        if self.member_type == "adult":
            if self.date_of_birth or self.guardian_member_id or self.invite_contact:
                raise ValueError(
                    "Adults do not give a date of birth, guardian or invite contact"
                )
            if not self.phone_number and not self.email:
                raise ValueError("An adult needs a phone number or an email to receive the invite")
            if self.household_id is None:
                raise ValueError("An adult needs a household_id")
        else:  # minor
            if self.date_of_birth is None:
                raise ValueError("A minor needs a date of birth")
            if self.phone_number or self.email:
                raise ValueError(
                    "A minor has no login contact. Use invite_contact for a parent or guardian's phone or email"
                )
            if self.household_id is None and self.guardian_member_id is None:
                raise ValueError("A minor needs a household_id or a guardian_member_id")
        return self


class InviteContactRequest(BaseModel):
    invite_contact: str

    @field_validator("invite_contact")
    @classmethod
    def clean(cls, v):
        return normalize_contact(v)


class DateOfBirthLookupRequest(BaseModel):
    # Every lookup is audited with this reason, so it has to say something real.
    reason: str = Field(min_length=10, max_length=300)


# --- Responses ---

class MemberResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    name: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    id_number: Optional[str] = None
    category: Optional[str] = None
    is_active: bool
    age_group: Literal["adult", "minor"]   # never the date of birth
    activated: bool                         # has set a password
    created_at: datetime

    @classmethod
    def from_member(cls, m, **extra):
        return cls(
            id=m.id,
            household_id=m.household_id,
            name=m.name,
            phone_number=m.phone_number,
            email=m.email,
            id_number=m.id_number,
            category=m.category,
            is_active=m.is_active,
            age_group="minor" if m.is_minor else "adult",
            activated=m.hashed_password is not None,
            created_at=m.created_at,
            **extra,
        )


class MemberOnboardResponse(MemberResponse):
    invite_sent: bool


class MemberMeResponse(MemberResponse):
    roles: List[str]


class DateOfBirthLookupResponse(BaseModel):
    member_id: uuid.UUID
    name: str
    date_of_birth: Optional[date] = None   # None for adults: no date of birth is kept for them
    age: Optional[int] = None


class MessageResponse(BaseModel):
    detail: str