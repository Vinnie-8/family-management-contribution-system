"""
Campaign — raises money (fixed/AGM, pledge-based, or emergency). See
FR3.1-3.7. type/status are plain strings for now (not a DB enum) so new
campaign types don't require a schema migration — validated at the
Pydantic schema layer instead.
"""
import uuid

from sqlalchemy import Boolean, Column, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    financial_year_id = Column(UUID(as_uuid=True), ForeignKey("financial_years.id"), nullable=False, index=True)

    type = Column(String, nullable=False)  # "fixed" | "pledge" | "emergency" | "standing"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    target_amount = Column(Numeric(12, 2), nullable=True)  # null for pledge-based (no fixed target)
    includes_minors = Column(Boolean, nullable=False, default=False)  # explicit opt-in (Decision Log)
    status = Column(String, nullable=False, default="open")  # "open" | "closed"

    contribution_rules = relationship("ContributionRule", back_populates="campaign")