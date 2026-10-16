import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class HouseHold(Base):
    __tablename__ = "households"
    __table_args__ = (
        CheckConstraint(
            "parent_household_id IS NULL OR parent_household_id <> id",
            name="check_household_not_own_parent",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)

    head_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="SET NULL", use_alter=True, name="fk_households_head_member"),
        nullable=True,
    )
    parent_household_id = Column(
        UUID(as_uuid=True),
        ForeignKey("households.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    family = relationship("Family", back_populates="households")