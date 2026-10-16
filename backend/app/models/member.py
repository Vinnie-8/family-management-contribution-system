import uuid

from sqlalchemy import Column, ForeignKey, String, Boolean, CheckConstraint, DateTime, Date
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base
from app.core.age import age_in_years


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        # A member who has a password must have somewhere to be reached / to log in with.
        CheckConstraint(
            "hashed_password IS NULL OR phone_number IS NOT NULL OR email IS NOT NULL",
            name="check_password_needs_contact",
        ),
        # An invite contact only makes sense for minors, who are the ones with a date of birth.
        CheckConstraint(
            "invite_contact IS NULL OR date_of_birth IS NOT NULL",
            name="check_invite_contact_minors_only",
        ),
        CheckConstraint(
            r"phone_number IS NULL OR phone_number ~ '^\+254[17][0-9]{8}$'",
            name="check_phone_format",
        ),
        CheckConstraint(
            "id_number IS NULL OR id_number ~ '^[0-9]{8}$'",
            name="check_id_number_format",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    # Required: every member belongs to exactly one household.
    # RESTRICT stops a household being deleted while it still has members.
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id", ondelete="RESTRICT"), nullable=False, index=True)

    name = Column(String(100), nullable=False)
    id_number = Column(String(8), nullable=True, unique=True)
    phone_number = Column(String(13), nullable=True, unique=True)
    email = Column(String(50), nullable=True, unique=True)
    category = Column(String(50), nullable=True)

    # Minors only. Private. Cleared when the member activates their account.
    date_of_birth = Column(Date, nullable=True)
    # Minors only. Parent/guardian phone or email for the automatic activation link.
    invite_contact = Column(String(50), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    hashed_password = Column(String, nullable=True)  # NULL = not activated yet
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    family = relationship("Family", back_populates="members")
    member_roles = relationship("MemberRole", back_populates="member", foreign_keys="[MemberRole.member_id]")
    
    
    @property
    def is_minor(self) -> bool:
       """Computed, never stored. Adults have no date_of_birth, so they are never minors."""
       if self.date_of_birth is None:
           return False
       return age_in_years(self.date_of_birth) < self.family.age_of_majority
