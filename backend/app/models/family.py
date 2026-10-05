import uuid
from sqlalchemy import DateTime,Column,String
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base

class Family(Base):
    __tablename__ = "families"
    
    id = Column(UUID(as_uuid=True),primary_key = True , default = uuid.uuid4)
    name = Column(String, nullable = False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(),nullable=False)
    members = relationship("Member", back_populates="family")
    