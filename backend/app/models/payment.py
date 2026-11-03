"""
Payment — the single table for cash, bank transfer, M-Pesa, AND in-kind
payments ("a hen is not cash... this keeps a single payment table instead of
splitting cash and in-kind into separate flows").

Exactly one target: a pledge, a fine, or the welfare fund (database CHECK).
amount is always the KES value; for in-kind the Treasurer enters the value and
item_description says what was given.

member_id is who the payment counts for; paid_by is who actually paid (a parent
for a child, say). recorded_by is who entered it; confirmed_by who confirmed it.

Money rows are never edited or deleted: a mistake is voided with a reason.
mpesa_transaction_code is unique, so a retried or duplicate M-Pesa entry can
never create a second payment (FR6.4). idempotency_key is unique per family, so
a double-submit returns the first payment (NFR: Resilience).
"""
import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "(pledge_id IS NOT NULL)::int + (fine_id IS NOT NULL)::int + (standing_fund_id IS NOT NULL)::int = 1",
            name="check_payment_one_target",
        ),
        CheckConstraint("amount > 0", name="check_payment_amount_positive"),
        UniqueConstraint("family_id", "idempotency_key", name="uq_payment_family_idempotency"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)

    # Exactly one of these three is set.
    pledge_id = Column(UUID(as_uuid=True), ForeignKey("pledges.id"), nullable=True, index=True)
    fine_id = Column(UUID(as_uuid=True), ForeignKey("fines.id"), nullable=True, index=True)
    standing_fund_id = Column(UUID(as_uuid=True), ForeignKey("standing_funds.id"), nullable=True, index=True)

    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False, index=True)  # counts for
    paid_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)  # actually paid

    method = Column(String, nullable=False)  # "bank_transfer" | "cash" | "mpesa" | "in_kind"
    amount = Column(Numeric(12, 2), nullable=False)  # KES value
    item_description = Column(String, nullable=True)  # for in_kind (FR6.2)

    mpesa_transaction_code = Column(String, nullable=True, unique=True)  # FR6.4
    idempotency_key = Column(String, nullable=True)  # unique per family, see __table_args__

    status = Column(String, nullable=False, default="pending")  # "pending" | "confirmed" | "rejected" | "voided"
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    confirmed_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True)  # Treasurer/Chairman (FR6.5)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    reject_reason = Column(String(300), nullable=True)
    voided_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True)
    voided_at = Column(DateTime(timezone=True), nullable=True)
    void_reason = Column(String(300), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)