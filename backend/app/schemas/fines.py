"""Request/response schemas for fines."""
import uuid
import datetime as dt
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.clock import today_local
from app.schemas.common import empty_to_none
from app.schemas.money import Money
from app.schemas.reasons import Reason


class FineCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    member_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=200, description="e.g. Missed the AGM")
    amount: Money
    # Leave out for today. A fine can't be dated in the future.
    date: Optional[dt.date] = None

    @field_validator("date", mode="before")
    @classmethod
    def blank_date_to_none(cls, v):
        return empty_to_none(v)

    @field_validator("date")
    @classmethod
    def not_future(cls, v):
        if v is not None and v > today_local():
            raise ValueError("A fine can't be dated in the future")
        return v


class FineActionRequest(BaseModel):
    """Waive or void a fine."""
    reason: Reason


class FineResponse(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    member_name: str
    reason: str
    amount: Decimal
    fulfilled_amount: Decimal
    outstanding: Decimal
    date: dt.date
    status: str
    financial_year_id: uuid.UUID
    recorded_by: uuid.UUID
    waive_reason: Optional[str] = None
    void_reason: Optional[str] = None
    created_at: datetime

    @classmethod
    def from_fine(cls, f, member_name: str):
        closed = f.status in ("waived", "voided")
        return cls(
            id=f.id,
            member_id=f.member_id,
            member_name=member_name,
            reason=f.reason,
            amount=f.amount,
            fulfilled_amount=f.fulfilled_amount,
            outstanding=Decimal("0.00") if closed else f.amount - f.fulfilled_amount,
            date=f.date,
            status=f.status,
            financial_year_id=f.financial_year_id,
            recorded_by=f.recorded_by,
            waive_reason=f.waive_reason,
            void_reason=f.void_reason,
            created_at=f.created_at,
        )