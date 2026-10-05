"""
GuardianLink — the ONE place the guardian/minor relationship is explicit
(per Data Model doc). Everything else (Pledge, Payment, Attendance) points
at Member as usual for both adults and minors; this table is purely the
mapping of "who speaks/pays for whom."
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class GuardianLink(Base):
    __tablename__ = "guardian_links"
    __table_args__ = (
        # A guardian can be linked to the same minor only once (though one
        # minor could theoretically have links to multiple guardians, and
        # one guardian to multiple minors — this only forbids duplicates).
        UniqueConstraint("guardian_member_id", "minor_member_id", name="uq_guardian_minor"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guardian_member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False, index=True)
    minor_member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False, index=True)
    relationship_label = Column(String, nullable=True)  # e.g. "mother", "father", "uncle"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)