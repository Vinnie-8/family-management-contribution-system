"""Request/response schemas for pledges and installments."""
import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.schemas.common import empty_to_none
from app.schemas.money import Money
from app.schemas.reasons import Reason


# --- Requests ---

class MyPledgeRequest(BaseModel):
    """A member pledges to (or changes their pledge on) a pledge or emergency campaign."""
    amount: Money


class RecordPledgeRequest(BaseModel):
    """An officer records a pledge for a member who can't do it themselves."""
    campaign_id: uuid.UUID
    member_id: uuid.UUID
    amount: Money
    # Who made the commitment. Leave out for the member themselves (or a minor's guardian).
    pledged_by: Optional[uuid.UUID] = None

    @field_validator("pledged_by", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return empty_to_none(v)


class InstallmentItem(BaseModel):
    amount: Money
    due_date: date


class SetInstallmentsRequest(BaseModel):
    # Replaces the whole plan. An empty list clears it. The amounts must add up to the pledge.
    installments: List[InstallmentItem]

    @model_validator(mode="after")
    def dates_unique(self):
        dates = [i.due_date for i in self.installments]
        if len(dates) != len(set(dates)):
            raise ValueError("Two installments cannot have the same due date")
        return self


class CancelPledgeRequest(BaseModel):
    reason: Reason


# --- Responses ---

class InstallmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Decimal
    due_date: date
    status: str


class PledgeSummary(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    campaign_name: str
    campaign_type: str
    member_id: uuid.UUID
    member_name: str
    pledged_by: uuid.UUID
    source: str
    amount: Decimal
    fulfilled_amount: Decimal
    outstanding: Decimal
    status: str
    installments: List[InstallmentResponse] = []

    @classmethod
    def from_view(cls, v):
        p = v.pledge
        return cls(
            id=p.id,
            campaign_id=p.campaign_id,
            campaign_name=v.campaign_name,
            campaign_type=v.campaign_type,
            member_id=p.member_id,
            member_name=v.member_name,
            pledged_by=p.pledged_by,
            source=p.source,
            amount=p.amount,
            fulfilled_amount=p.fulfilled_amount,
            outstanding=p.amount - p.fulfilled_amount,
            status=p.status,
            installments=[InstallmentResponse.model_validate(i) for i in v.installments],
        )