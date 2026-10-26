"""
ContributionRule — per-category amounts as DATA, not hardcoded logic
(FR2.1). Adding a new member category or changing an amount is a row
insert/update, never a code deployment.

cash_amount is always the KES value. in_kind_item means "this item is
accepted instead of cash" (FR2.2), so every pledge has a money amount.
A rule with member_category "default" applies to any member whose category
has no rule of its own.
"""
import uuid

from sqlalchemy import CheckConstraint, Column, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ContributionRule(Base):
    __tablename__ = "contribution_rules"
    __table_args__ = (
        UniqueConstraint("campaign_id", "member_category", name="uq_rule_campaign_category"),
        CheckConstraint("cash_amount > 0", name="check_rule_cash_positive"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True)

    member_category = Column(String(50), nullable=False)  # e.g. "male", "female", or "default"
    cash_amount = Column(Numeric(12, 2), nullable=False)  # the KES value
    in_kind_item = Column(String, nullable=True)  # e.g. "one hen" (FR2.2)

    campaign = relationship("Campaign", back_populates="contribution_rules")