"""
Expense — money going OUT, tagged against an event/category (for
budget-vs-actual comparison, FR4.4) or a standing fund. beneficiary_member_id
is optional (FR7.2) — e.g. bereavement support paid to a specific member,
useful both for welfare-fund payouts and year-end reporting.
"""
import uuid

from sqlalchemy import Column, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    financial_year_id = Column(UUID(as_uuid=True), ForeignKey("financial_years.id"), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=True, index=True)
    standing_fund_id = Column(UUID(as_uuid=True), ForeignKey("standing_funds.id"), nullable=True, index=True)
    beneficiary_member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True)

    category = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    date = Column(Date, nullable=False)

    recorded_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)  # Treasurer (FR7.1)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True)