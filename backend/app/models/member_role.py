
""" MemberRole — many-to-many join between Member and Role. Lets a member
 hold multiple roles simultaneously (e.g. Chairman AND Guardian).
 """
 
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class MemberRole(Base):
    __tablename__ = "member_roles"
    __table_args__ = (
        UniqueConstraint("member_id", "role_id", name="uq_member_role"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False, index=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False, index=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    member = relationship("Member", back_populates="member_roles", foreign_keys=[member_id])
    role = relationship("Role", back_populates="member_roles")