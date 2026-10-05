"""
ContributionRule — per-category amounts as DATA, not hardcoded logic
(FR2.1). Adding a new member category or changing an amount is a row
insert/update, never a code deployment.
"""
import uuid

from sqlalchemy import Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ContributionRule(Base):
    __tablename__ = "contribution_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True)

    member_category = Column(String, nullable=False)  # e.g. "male", "female"
    cash_amount = Column(Numeric(12, 2), nullable=True)
    in_kind_item = Column(String, nullable=True)  # e.g. "one hen" (FR2.2)

    campaign = relationship("Campaign", back_populates="contribution_rules")