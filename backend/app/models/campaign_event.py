"""
CampaignEvent — junction table for the Campaign <-> Event many-to-many
relationship ("one event can be funded by several campaigns, and a single
broad campaign could contribute toward more than one event").

allocated_amount is optional: when the Chairman sets it, each event shows what
it was allocated and what has been spent. The allocations of one campaign
across all events may not exceed its target (checked in event_service).
"""
import uuid

from sqlalchemy import CheckConstraint, Column, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class CampaignEvent(Base):
    __tablename__ = "campaign_events"
    __table_args__ = (
        UniqueConstraint("campaign_id", "event_id", name="uq_campaign_event"),
        CheckConstraint("allocated_amount IS NULL OR allocated_amount > 0", name="check_campaign_event_allocation_positive"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False, index=True)
    allocated_amount = Column(Numeric(12, 2), nullable=True)