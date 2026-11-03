"""
StandingFund — an always-open welfare/emergency fund with no end_date and
no target, structurally different from Campaign's time-boxed shape
(Data Model doc). One per family, created the first time it is needed.

balance goes up when a confirmed payment (or a fine payment) comes in and down
when an approved expense is drawn on it; voids reverse both. Only
payment_service and expense_service change it, inside the same transaction and
after locking the row. The database refuses a negative balance.
"""
import uuid

from sqlalchemy import CheckConstraint, Column, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class StandingFund(Base):
    __tablename__ = "standing_funds"
    __table_args__ = (
        UniqueConstraint("family_id", name="uq_standing_fund_family"),
        CheckConstraint("balance >= 0", name="check_standing_fund_balance_not_negative"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    name = Column(String, nullable=False, default="Welfare Fund")
    balance = Column(Numeric(12, 2), nullable=False, default=0)