"""
FinancialYear — the reporting period boundary (per Data Model doc).
Campaign and Expense both reference the FinancialYear they belong to, so
the annual report (FR12.4) is a filtered aggregation query against this
table's id, not a bespoke calculation.
"""
import uuid

from sqlalchemy import Column, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class FinancialYear(Base):
    __tablename__ = "financial_years"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)

    # Numeric(12, 2): fixed-point decimal, never Float — required for money
    # per Non-Functional Requirements (no floating-point rounding in financial records).
    opening_balance = Column(Numeric(12, 2), nullable=False, default=0)
    closing_balance = Column(Numeric(12, 2), nullable=True)  # set only once the year is closed