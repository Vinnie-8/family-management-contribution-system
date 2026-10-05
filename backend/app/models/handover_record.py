"""
HandoverRecord — leadership term/election handover (FR10.1-10.3). Built
as a proper state machine (pending -> confirmed -> active), not a one-off
admin action, because this flow runs repeatedly over the system's life
(3-year terms) and must prevent a moment where either both people have
full admin rights simultaneously, or neither does (Security & Privacy doc).
"""
import uuid

from sqlalchemy import Column, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class HandoverRecord(Base):
    __tablename__ = "handover_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role = Column(String, nullable=False)  # "chairman" | "secretary" | "treasurer"

    outgoing_member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True)  # null: first holder
    incoming_member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)

    term_start = Column(Date, nullable=False)
    term_end = Column(Date, nullable=True)  # set once the NEXT handover happens

    # "pending": incoming assigned, outgoing hasn't confirmed yet
    # "confirmed": outgoing confirmed, incoming's permissions now active
    # "active": current holder of this role
    # "ended": superseded by a later HandoverRecord for the same role
    status = Column(String, nullable=False, default="pending")