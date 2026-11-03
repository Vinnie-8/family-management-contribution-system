"""Request/response schemas for expenses."""
import uuid
import datetime as dt
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.clock import today_local
from app.schemas.common import empty_to_none
from app.schemas.money import Money
from app.schemas.reasons import Reason

# A fixed list, so reports group cleanly ("Transport" and "transport" are one category).
ExpenseCategory = Literal[
    "transport", "food", "venue", "bereavement_support", "medical",
    "printing", "gifts", "communication", "other",
]


class ExpenseCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # Exactly one source: an event, or the welfare fund.
    event_id: Optional[uuid.UUID] = None
    from_standing_fund: bool = False

    category: ExpenseCategory
    description: Optional[str] = Field(default=None, max_length=200)
    amount: Money
    date: Optional[dt.date] = None  # leave out for today
    beneficiary_member_id: Optional[uuid.UUID] = None  # e.g. bereavement support paid to a member

    @field_validator("event_id", "description", "date", "beneficiary_member_id", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return empty_to_none(v)

    @field_validator("date")
    @classmethod
    def not_future(cls, v):
        if v is not None and v > today_local():
            raise ValueError("An expense can't be dated in the future")
        return v

    @model_validator(mode="after")
    def exactly_one_source(self):
        if (self.event_id is not None) + bool(self.from_standing_fund) != 1:
            raise ValueError("Give exactly one of event_id, or from_standing_fund: true")
        return self


class ExpenseActionRequest(BaseModel):
    """Reject or void an expense."""
    reason: Reason


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    event_id: Optional[uuid.UUID] = None
    standing_fund_id: Optional[uuid.UUID] = None
    beneficiary_member_id: Optional[uuid.UUID] = None
    category: str
    description: Optional[str] = None
    amount: Decimal
    date: dt.date
    status: str
    recorded_by: uuid.UUID
    approved_by: Optional[uuid.UUID] = None
    approved_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
    void_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)