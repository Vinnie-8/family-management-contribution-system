"""
Notification — in-app + SMS records (FR13.1-13.3). For a Minor Member's
pledges/payments, notifications route to the linked Guardian's contact
details (FR13.3) — that routing logic lives in the service layer;
recipient_member_id here is simply whoever the notification is actually
FOR, already resolved (i.e. the Guardian, not the minor).
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False, index=True)

    type = Column(String, nullable=False)  # e.g. "campaign_ending_soon", "payment_confirmed", "meeting_notice"
    channel = Column(String, nullable=False, default="in_app")  # "in_app" | "sms"
    message = Column(Text, nullable=False)

    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)