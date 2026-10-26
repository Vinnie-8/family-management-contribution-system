"""
Pledge — a member's commitment against a campaign (FR5.1-5.4).

Two sources:
  "assessed"  - created automatically when a fixed campaign opens (the obligation)
  "voluntary" - chosen by the member, or recorded for them by an officer

pledged_by is who made the commitment (a guardian, for a minor).
fulfilled_amount is maintained incrementally as payments are confirmed or
voided; only payment_service changes it, inside the same transaction and
after locking the row. A reconcile script recomputes it from the payments.
"""
import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Pledge(Base):
    __tablename__ = "pledges"
    __table_args__ = (
        UniqueConstraint("member_id", "campaign_id", name="uq_pledge_member_campaign"),
        CheckConstraint("amount > 0", name="check_pledge_amount_positive"),
        CheckConstraint("fulfilled_amount >= 0", name="check_pledge_fulfilled_not_negative"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False, index=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True)
    pledged_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)

    source = Column(String, nullable=False)  # "assessed" | "voluntary"
    amount = Column(Numeric(12, 2), nullable=False)
    fulfilled_amount = Column(Numeric(12, 2), nullable=False, default=0)  # changed only by payment_service
    status = Column(String, nullable=False, default="active")  # "active" | "fulfilled" | "cancelled"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    installments = relationship("PledgeInstallment", back_populates="pledge")