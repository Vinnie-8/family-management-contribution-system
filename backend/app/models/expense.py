"""
Expense — money going OUT, tagged against an event/category (for
budget-vs-actual comparison, FR4.4) or the welfare fund. beneficiary_member_id
is optional (FR7.2) — e.g. bereavement support paid to a specific member.

Exactly one source: an event or the welfare fund (database CHECK).
Status: pending -> approved (Chairman) or rejected. An approved expense can be
voided. Only an approved expense counts in any balance; approving a welfare-fund
expense lowers the fund, and the approver must be someone other than the recorder.
"""
import uuid

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint(
            "(event_id IS NOT NULL)::int + (standing_fund_id IS NOT NULL)::int = 1",
            name="check_expense_one_source",
        ),
        CheckConstraint("amount > 0", name="check_expense_amount_positive"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    financial_year_id = Column(UUID(as_uuid=True), ForeignKey("financial_years.id"), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=True, index=True)
    standing_fund_id = Column(UUID(as_uuid=True), ForeignKey("standing_funds.id"), nullable=True, index=True)
    beneficiary_member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True)

    category = Column(String, nullable=False)  # validated against a fixed list in the schema layer
    description = Column(String(200), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    date = Column(Date, nullable=False)

    status = Column(String, nullable=False, default="pending")  # "pending" | "approved" | "rejected" | "voided"
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)  # Treasurer (FR7.1)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    reject_reason = Column(String(300), nullable=True)
    voided_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True)
    voided_at = Column(DateTime(timezone=True), nullable=True)
    void_reason = Column(String(300), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)