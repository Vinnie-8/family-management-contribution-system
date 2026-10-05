"""
Pledge — a member's (or their Guardian's, on their behalf) commitment
against a pledge-based campaign (FR5.1-5.4). fulfilled_amount is
maintained incrementally as payments are confirmed (NFR: Performance —
updated on each confirmed transaction, not a live SUM() on every page load).
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Pledge(Base):
    __tablename__ = "pledges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False, index=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True)

    amount = Column(Numeric(12, 2), nullable=False)
    fulfilled_amount = Column(Numeric(12, 2), nullable=False, default=0)  # incremented on each confirmed payment
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    installments = relationship("PledgeInstallment", back_populates="pledge")