"""Request/response schemas for events and event funding."""
import uuid
from datetime import date
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import empty_to_none
from app.schemas.money import Money


class EventCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=300)
    event_date: date
    budget_amount: Optional[Money] = None

    @field_validator("description", "budget_amount", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return empty_to_none(v)


class EventUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=300)
    event_date: Optional[date] = None
    budget_amount: Optional[Money] = None
    status: Optional[Literal["planned", "held", "closed"]] = None

    @field_validator("name", "description", "event_date", "budget_amount", "status", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return empty_to_none(v)

    @model_validator(mode="after")
    def something_to_change(self):
        if not self.model_fields_set or all(getattr(self, f) is None for f in self.model_fields_set):
            raise ValueError("Send at least one field to change")
        return self


class CampaignLink(BaseModel):
    campaign_id: uuid.UUID
    # How much of that campaign's money is meant for this event. Optional.
    allocated_amount: Optional[Money] = None

    @field_validator("allocated_amount", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return empty_to_none(v)


class LinkCampaignsRequest(BaseModel):
    # Replaces all links of the event. An empty list removes them.
    links: List[CampaignLink]

    @model_validator(mode="after")
    def campaigns_unique(self):
        ids = [l.campaign_id for l in self.links]
        if len(ids) != len(set(ids)):
            raise ValueError("A campaign can be linked to an event only once")
        return self


class LinkedCampaign(BaseModel):
    campaign_id: uuid.UUID
    campaign_name: str
    allocated_amount: Optional[Decimal] = None
    collected: Decimal  # paid so far on that campaign, in total, not split between events


class EventResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    event_date: date
    budget_amount: Optional[Decimal] = None
    status: str
    campaigns: List[LinkedCampaign] = []
    allocated_total: Decimal = Decimal("0.00")
    spent_total: Decimal = Decimal("0.00")         # approved expenses only
    remaining_allocation: Optional[Decimal] = None  # null when no allocations are set
    remaining_budget: Optional[Decimal] = None      # null when no budget is set

    @classmethod
    def from_detail(cls, d: dict):
        e = d["event"]
        return cls(
            id=e.id,
            name=e.name,
            description=e.description,
            event_date=e.event_date,
            budget_amount=e.budget_amount,
            status=e.status,
            campaigns=[LinkedCampaign(**c) for c in d["campaigns"]],
            allocated_total=d["allocated_total"],
            spent_total=d["spent_total"],
            remaining_allocation=d["remaining_allocation"],
            remaining_budget=d["remaining_budget"],
        )