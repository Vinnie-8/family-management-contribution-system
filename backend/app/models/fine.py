"""
Fine — recorded against a member (e.g. missed meeting, late payment).
Contributes to family totals but is aggregate-only to other members,
same privacy rule as any other individual financial record (FR8.2).
"""
import uuid

from sqlalchemy import Column, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Fine(Base):
    __tablename__ = "fines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False, index=True)

    reason = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    date = Column(Date, nullable=False)