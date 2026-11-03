"""
PledgeInstallment — its own child entity (not just amount+date on Pledge)
because recurring monthly collection toward one deadline needs per-installment
due dates and status (Data Model doc, FR5.4).

Installments are not paid one by one. Payments apply oldest-first: an
installment counts as paid when the pledge's fulfilled_amount covers it and all
earlier ones. pledge_service recomputes the statuses; a daily job marks overdue.
The installments of a pledge always add up exactly to the pledge amount.
"""
import uuid

from sqlalchemy import CheckConstraint, Column, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class PledgeInstallment(Base):
    __tablename__ = "pledge_installments"
    __table_args__ = (
        UniqueConstraint("pledge_id", "due_date", name="uq_installment_pledge_due_date"),
        CheckConstraint("amount > 0", name="check_installment_amount_positive"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pledge_id = Column(UUID(as_uuid=True), ForeignKey("pledges.id"), nullable=False, index=True)

    amount = Column(Numeric(12, 2), nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="pending")  # "pending" | "paid" | "overdue"

    pledge = relationship("Pledge", back_populates="installments")