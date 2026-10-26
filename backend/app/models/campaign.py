"""
Campaign — raises money (fixed, pledge-based, or emergency). See FR3.1-3.7.
type/status are plain strings (not a DB enum) so new campaign types don't
require a schema migration — validated at the Pydantic schema layer instead.

Lifecycle: draft -> open -> closed, or cancelled from draft/open.
The always-open welfare fund is NOT a campaign; it is the StandingFund table.
"""
import uuid

from sqlalchemy import Boolean, CheckConstraint, Column, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="check_campaign_dates"),
        CheckConstraint("target_amount IS NULL OR target_amount > 0", name="check_campaign_target_positive"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    financial_year_id = Column(UUID(as_uuid=True), ForeignKey("financial_years.id"), nullable=False, index=True)
    # Null only for rows created before this column existed; the service always sets it.
    created_by = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True)

    name = Column(String(100), nullable=False)
    type = Column(String, nullable=False)  # "fixed" | "pledge" | "emergency"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    target_amount = Column(Numeric(12, 2), nullable=True)  # null for pledge-based (no fixed target)
    includes_minors = Column(Boolean, nullable=False, default=False)  # explicit opt-in (Decision Log)
    status = Column(String, nullable=False, default="draft")  # "draft" | "open" | "closed" | "cancelled"

    contribution_rules = relationship("ContributionRule", back_populates="campaign")