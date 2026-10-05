"""
PledgeInstallment — its own child entity (not just amount+date on Pledge)
because recurring monthly AGM collection toward one annual deadline needs
per-installment due dates and fulfillment status (Data Model doc, FR5.4).
"""
import uuid

from sqlalchemy import Column, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class PledgeInstallment(Base):
    __tablename__ = "pledge_installments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pledge_id = Column(UUID(as_uuid=True), ForeignKey("pledges.id"), nullable=False, index=True)

    amount = Column(Numeric(12, 2), nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="pending")  # "pending" | "paid" | "overdue"

    pledge = relationship("Pledge", back_populates="installments")