"""
Document — a reusable polymorphic attachment table (Data Model doc):
"backs published budgets, expense receipts, dispute evidence, and minutes
attachments — one mechanism instead of four." NOTE: like CampaignEvent,
this table isn't in the original scaffold's model file list — it's added
here because the Data Model doc explicitly calls for it by name as a
generic mechanism, rather than one bespoke attachment table per feature.

entity_type + entity_id together point at "whatever this attaches to"
(e.g. entity_type="budget", entity_id=<that budget's id>) — there's no
database-level FK here, since entity_type varies; integrity is enforced
in the service layer instead.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String, nullable=False, index=True)  # e.g. "budget", "expense", "dispute", "minutes_record"
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    file_url = Column(String, nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)