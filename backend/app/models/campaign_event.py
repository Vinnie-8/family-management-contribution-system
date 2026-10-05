"""
CampaignEvent — junction table for the Campaign <-> Event many-to-many
relationship (Data Model doc: "one event can be funded by several
campaigns, and a single broad campaign could contribute toward more than
one event"). NOTE: this table isn't in the original scaffold's model file
list — it's added here because the Data Model doc explicitly calls for a
join relationship rather than a foreign key on either side, which a
single FK on Campaign or Event cannot express.
"""
import uuid

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class CampaignEvent(Base):
    __tablename__ = "campaign_events"
    __table_args__ = (
        UniqueConstraint("campaign_id", "event_id", name="uq_campaign_event"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False, index=True)