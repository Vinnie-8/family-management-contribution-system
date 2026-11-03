"""
Event — what money is FOR (as opposed to Campaign, which is what money
is raised THROUGH). Linked to campaigns via the CampaignEvent join table,
since the relationship is many-to-many (Data Model doc).

Status: planned -> held -> closed. A closed event takes no new expenses.
"""
import uuid

from sqlalchemy import CheckConstraint, Column, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("budget_amount IS NULL OR budget_amount > 0", name="check_event_budget_positive"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    event_date = Column(Date, nullable=False)
    budget_amount = Column(Numeric(12, 2), nullable=True)  # optional, for budget-versus-actual (FR4.4)
    status = Column(String, nullable=False, default="planned")  # "planned" | "held" | "closed"