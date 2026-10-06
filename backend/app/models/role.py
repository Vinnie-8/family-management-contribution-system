import uuid
from sqlalchemy import Column,String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base 

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String,nullable=False,unique=True)
    description = Column(String,nullable = False)
    
    
    member_roles = relationship("MemberRole", back_populates = "role")
    
    
    