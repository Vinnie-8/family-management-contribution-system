"""
Budget — an event's spending plan, broken down by category, with a
draft -> approved -> published workflow (FR4.2). Only visible to members
once status == "published" — that check belongs in the service/router
layer, not here.
"""
import uuid

from sqlalchemy import Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False, index=True)

    category = Column(String, nullable=False)  # e.g. "venue", "food", "entertainment"
    planned_amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String, nullable=False, default="draft")  # "draft" | "approved" | "published"
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)