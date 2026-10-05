"""
MinutesRecord — recorded/edited/published/locked by Secretary (FR11.3).
Locked minutes are immutable: a further edit creates a NEW ROW with an
incremented version, rather than overwriting the locked one — this is
what makes "locked = preserved forever" actually true at the data level,
not just a UI restriction.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class MinutesRecord(Base):
    __tablename__ = "minutes_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False, index=True)

    content = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="draft")  # "draft" | "published" | "locked"

    created_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)