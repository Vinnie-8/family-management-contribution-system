"""
Meeting — created by Secretary (FR11.1). Attendance and MinutesRecord
both hang off this.
"""
import uuid

from sqlalchemy import Column, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)

    meeting_date = Column(Date, nullable=False)
    location = Column(String, nullable=True)
    agenda = Column(String, nullable=True)