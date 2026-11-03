"""
Fine — recorded against a member (e.g. missed meeting, late payment).
Contributes to family totals but is aggregate-only to other members, same
privacy rule as any other individual financial record (FR8.2).

A fine is collected through the same payments table (payment.fine_id) and its
money goes into the family's welfare fund. fulfilled_amount is changed only by
payment_service.

Status: unpaid -> partial -> paid. "waived" means the Chairman forgave a real
fine; "voided" means it was recorded by mistake. Both need a reason, and neither
is possible while the fine has payments.
"""
import uuid

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Fine(Base):
    __tablename__ = "fines"
    __table_args__ = (
        CheckConstraint("amount > 0", name="check_fine_amount_positive"),
        CheckConstraint("fulfilled_amount >= 0 AND fulfilled_amount <= amount", name="check_fine_fulfilled_range"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False, index=True)
    financial_year_id = Column(UUID(as_uuid=True), ForeignKey("financial_years.id"), nullable=False, index=True)
    standing_fund_id = Column(UUID(as_uuid=True), ForeignKey("standing_funds.id"), nullable=False)
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)

    reason = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    fulfilled_amount = Column(Numeric(12, 2), nullable=False, default=0)  # changed only by payment_service
    date = Column(Date, nullable=False)

    status = Column(String, nullable=False, default="unpaid")  # "unpaid" | "partial" | "paid" | "waived" | "voided"
    waive_reason = Column(String(300), nullable=True)
    voided_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True)
    voided_at = Column(DateTime(timezone=True), nullable=True)
    void_reason = Column(String(300), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)