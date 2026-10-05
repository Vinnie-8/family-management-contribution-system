"""
AuditLog — immutable record of every critical action (FR14.1). Written by
every service via audit_service.log_action(), never edited or deleted.
"""
import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.database import Base

# Single source of truth: import these in audit_service and schemas too.
AUDIT_ACTIONS = (
    "create",
    "update",
    "delete",
    "deactivate_member",
    "reset_password",
)
ENTITY_TYPES = (
    "member",
    "household",
    "contribution_rule",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        # Database-level backstop: only known actions / entity types can be
        # stored, even if a script or future code path bypasses audit_service.
        CheckConstraint(_in_list("action", AUDIT_ACTIONS), name="chk_audit_action"),
        CheckConstraint(_in_list("entity_type", ENTITY_TYPES), name="chk_audit_entity_type"),
        # Typical query: "show this family's history for one entity".
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True)
    # Nullable: system-triggered events (or failed logins) have no acting member.
    actor_member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=True, index=True)

    action = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    # No ForeignKey on purpose: it points at different tables depending on
    # entity_type, and audit rows must survive deletion of the entity.
    entity_id = Column(UUID(as_uuid=True), nullable=True)

    # Snapshots. Never include secrets such as hashed_password.
    before_state = Column(JSONB, nullable=True)
    after_state = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)