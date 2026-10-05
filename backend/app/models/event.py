"""
Event — what money is FOR (as opposed to Campaign, which is what money
is raised THROUGH). Linked to campaigns via the CampaignEvent join table,
since the relationship is many-to-many (Data Model doc).
"""
import uuid

from sqlalchemy import Column, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    event_date = Column(Date, nullable=False)