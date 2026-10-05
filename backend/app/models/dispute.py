"""
Dispute — a member flagging a payment as contested (FR9.1-9.3). Evidence
(bank slip, M-Pesa message, screenshot) is attached via the generic
Document table rather than a dedicated evidence column, so any future
attachment type reuses the same mechanism.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, index=True)
    raised_by_member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)

    status = Column(String, nullable=False, default="open")  # "open" | "under_review" | "resolved" | "rejected"
    resolution_notes = Column(String, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)