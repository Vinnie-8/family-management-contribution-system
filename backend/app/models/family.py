import uuid
from sqlalchemy import DateTime, Column, String, Integer, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Family(Base):
    __tablename__ = "families"
    __table_args__ = (
        CheckConstraint(
            "age_of_majority BETWEEN 1 AND 30",
            name="check_age_of_majority_range",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    age_of_majority = Column(Integer, nullable=False, default=18, server_default="18")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    members = relationship("Member", back_populates="family")
    households = relationship("HouseHold", back_populates="family")