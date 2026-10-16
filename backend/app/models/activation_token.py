"""
ActivationToken — a one-time secret that lets a newly onboarded member set
their first password. Only the SHA-256 hash is stored, never the token
itself, so a leaked database can't be used to activate accounts.
SHA-256 (not bcrypt) is correct here: the token is 32 random bytes, so there
is nothing to brute-force, and lookups need a fast, exact match.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class ActivationToken(Base):
    __tablename__ = "activation_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    sent_to = Column(String(50), nullable=True)  # the phone/email the link went to
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)  # set when consumed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)