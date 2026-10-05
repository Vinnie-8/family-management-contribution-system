"""
StandingFund — an always-open welfare/emergency fund with no end_date and
no target, structurally different from Campaign's time-boxed shape
(Data Model doc). balance is maintained incrementally: += on confirmed
Payment, -= on recorded Expense against it.
"""
import uuid

from sqlalchemy import Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class StandingFund(Base):
    __tablename__ = "standing_funds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    name = Column(String, nullable=False, default="Welfare Fund")
    balance = Column(Numeric(12, 2), nullable=False, default=0)