"""
FinancialYear — the reporting period boundary (per Data Model doc).
Each family sets its own start and end dates, because families run their
year differently. Campaign, Fine and Expense belong to the year whose dates
contain them, so the annual report (FR12.4) is a filtered aggregation query
against this table's id, not a bespoke calculation.

A family's years may not overlap (enforced in the service layer).
"""
import uuid

from sqlalchemy import (
    CheckConstraint, Column, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class FinancialYear(Base):
    __tablename__ = "financial_years"
    __table_args__ = (
        CheckConstraint("end_date > start_date", name="check_financial_year_dates"),
        UniqueConstraint("family_id", "year", name="uq_financial_year_family_year"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)  # the label, e.g. 2026

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="open")  # "open" | "closed"

    # Numeric(12, 2): fixed-point decimal, never Float — required for money
    # per Non-Functional Requirements (no floating-point rounding in financial records).
    opening_balance = Column(Numeric(12, 2), nullable=False, default=0)
    closing_balance = Column(Numeric(12, 2), nullable=True)  # set only once the year is closed