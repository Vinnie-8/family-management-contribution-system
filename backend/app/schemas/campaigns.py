"""Request/response schemas for campaigns, contribution rules and pledges."""
import uuid
from datetime import date
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import empty_to_none
from app.schemas.money import Money


# --- Requests ---

class CampaignCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    financial_year_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    type: Literal["fixed", "pledge", "emergency"]
    start_date: date
    end_date: date
    # Optional goal for the whole campaign. Pledge-based campaigns usually leave it out.
    target_amount: Optional[Money] = None
    # Fixed campaigns only: also assess minors (a guardian pays for them).
    includes_minors: bool = False

    @field_validator("target_amount", mode="before")
    @classmethod
    def blank_target_to_none(cls, v):
        return empty_to_none(v)

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class RuleItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    member_category: str = Field(min_length=1, max_length=50)
    cash_amount: Money
    in_kind_item: Optional[str] = Field(default=None, max_length=100)

    @field_validator("in_kind_item", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return empty_to_none(v)


class SetRulesRequest(BaseModel):
    # Replaces the whole rule set. Use member_category "default" for a fallback.
    rules: List[RuleItem] = Field(min_length=1)

    @model_validator(mode="after")
    def categories_unique(self):
        seen = set()
        for rule in self.rules:
            key = rule.member_category.casefold()
            if key in seen:
                raise ValueError(f"Category '{rule.member_category}' appears more than once")
            seen.add(key)
        return self


class AssessMemberRequest(BaseModel):
    member_id: uuid.UUID


# --- Responses ---

class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    member_category: str
    cash_amount: Decimal
    in_kind_item: Optional[str] = None


class CampaignResponse(BaseModel):
    id: uuid.UUID
    financial_year_id: uuid.UUID
    name: str
    type: str
    start_date: date
    end_date: date
    target_amount: Optional[Decimal] = None
    includes_minors: bool
    status: str
    # Totals over pledges that are not cancelled
    pledge_count: int = 0
    pledged_total: Decimal = Decimal("0.00")
    fulfilled_total: Decimal = Decimal("0.00")
    outstanding_total: Decimal = Decimal("0.00")

    @classmethod
    def from_campaign(cls, c, totals=None, **extra):
        count, pledged, fulfilled = totals if totals else (0, Decimal("0"), Decimal("0"))
        return cls(
            id=c.id,
            financial_year_id=c.financial_year_id,
            name=c.name,
            type=c.type,
            start_date=c.start_date,
            end_date=c.end_date,
            target_amount=c.target_amount,
            includes_minors=c.includes_minors,
            status=c.status,
            pledge_count=count,
            pledged_total=pledged,
            fulfilled_total=fulfilled,
            outstanding_total=pledged - fulfilled,
            **extra,
        )


class CampaignDetailResponse(CampaignResponse):
    rules: List[RuleResponse] = []


class OpenCampaignResponse(CampaignResponse):
    pledges_created: int


class PledgeResponse(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    member_name: str
    campaign_id: uuid.UUID
    pledged_by: uuid.UUID
    source: str
    amount: Decimal
    fulfilled_amount: Decimal
    outstanding: Decimal
    status: str

    @classmethod
    def from_pledge(cls, p, member_name: str):
        return cls(
            id=p.id,
            member_id=p.member_id,
            member_name=member_name,
            campaign_id=p.campaign_id,
            pledged_by=p.pledged_by,
            source=p.source,
            amount=p.amount,
            fulfilled_amount=p.fulfilled_amount,
            outstanding=p.amount - p.fulfilled_amount,
            status=p.status,
        )