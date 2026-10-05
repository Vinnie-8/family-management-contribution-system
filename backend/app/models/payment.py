"""
Payment — the single table for cash, bank transfer, M-Pesa, AND in-kind
payments (Data Model doc: "a hen is not cash... this keeps a single
payment table instead of splitting cash and in-kind into separate
flows"). Exactly one of pledge_id / standing_fund_id is set, never both —
enforce that in the service layer (a CHECK constraint could also do this,
added later once the ORM-level logic is proven correct).

mpesa_transaction_code has a unique constraint so a retried/duplicate
M-Pesa callback can never create a second payment row (FR6.4, idempotency).
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pledge_id = Column(UUID(as_uuid=True), ForeignKey("pledges.id"), nullable=True, index=True)
    standing_fund_id = Column(UUID(as_uuid=True), ForeignKey("standing_funds.id"), nullable=True, index=True)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False, index=True)

    method = Column(String, nullable=False)  # "bank_transfer" | "cash" | "mpesa" | "in_kind"
    amount = Column(Numeric(12, 2), nullable=False)
    item_description = Column(String, nullable=True)  # for in_kind (FR6.2)

    mpesa_transaction_code = Column(String, nullable=True, unique=True)  # FR6.4
    status = Column(String, nullable=False, default="pending")  # "pending" | "confirmed" | "rejected"
    confirmed_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True)  # Treasurer/Chairman (FR6.5)

    idempotency_key = Column(String, nullable=True, unique=True)  # NFR: Resilience — protects against double-submit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)