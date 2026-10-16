"""Request/response schemas for households."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class HouseholdCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    # The household this one branched from, e.g. a married son's household
    # points at his parents'. Leave out for a top-level household.
    parent_household_id: Optional[uuid.UUID] = None


class SetHeadRequest(BaseModel):
    member_id: uuid.UUID


class AddMemberRequest(BaseModel):
    member_id: uuid.UUID


class HouseholdResponse(BaseModel):
    id: uuid.UUID
    name: str
    head_member_id: Optional[uuid.UUID] = None
    parent_household_id: Optional[uuid.UUID] = None
    member_count: int
    created_at: datetime

    @classmethod
    def from_household(cls, h, member_count: int):
        return cls(
            id=h.id,
            name=h.name,
            head_member_id=h.head_member_id,
            parent_household_id=h.parent_household_id,
            member_count=member_count,
            created_at=h.created_at,
        )