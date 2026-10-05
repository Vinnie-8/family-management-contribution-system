import uuid
from sqlalchemy import Column,ForeignKey,String,Boolean,CheckConstraint,DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base

class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        CheckConstraint("is_minor = True OR phone_number IS NOT NULL OR email IS NOT NULL",
                         name ="check_adult_has_contact",
                         ),
         CheckConstraint(
        "phone_number IS NULL OR phone_number ~ '^[0-9]{10}$'",
        name="check_phone_format",
    ),
    CheckConstraint(
        "id_number IS NULL OR id_number ~ '^[0-9]{8}$'",
        name="check_id_number_format"
                   ),
    )
    
    id = Column(UUID(as_uuid=True), primary_key = True, default = uuid.uuid4)
    family_id = Column(UUID(as_uuid = True),ForeignKey("families.id",ondelete="CASCADE"),nullable=False,index=True)
    household_id = Column(UUID(as_uuid = True),ForeignKey("households.id",ondelete="SET NULL"),nullable=True,index=True)
    
    name = Column(String(100),nullable = False)
    id_number = Column(String(8), nullable = True , unique=True)
    phone_number = Column(String(13), nullable = True,unique=True)
    email = Column(String(50),nullable = True,unique = True)
    category = Column(String(50), nullable = True)
    
    is_minor = Column(Boolean,nullable=False,default=False)
    is_active = Column(Boolean,nullable=False,default=True)
    hashed_password = Column(String, nullable=True)
    must_change_password = Column(Boolean, nullable=False, default=False)
    password_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True),server_default = func.now(),nullable=False)
    
    family = relationship("Family", back_populates = "members")
    member_roles = relationship("MemberRole", back_populates = "member",foreign_keys=["MemberRole.member_id"])
    
    
 
    