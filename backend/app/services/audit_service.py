import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AUDIT_ACTIONS, ENTITY_TYPES, AuditLog

# Audit snapshots must never hold credentials or a date of birth.
_FORBIDDEN_KEYS = {"hashed_password", "date_of_birth", "password", "token"}


def log_action(
    db: Session,
    *,
    family_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: Optional[uuid.UUID] = None,
    actor_member_id: Optional[uuid.UUID] = None,
    before_state: Optional[dict] = None,
    after_state: Optional[dict] = None,
) -> AuditLog:
    """Writes one audit entry. Does NOT commit: it saves with the caller's
    transaction. Flush new entities first so entity_id is not None."""
    if action not in AUDIT_ACTIONS:
        raise ValueError(f"Unknown audit action: {action!r}")
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"Unknown audit entity type: {entity_type!r}")
    for state in (before_state, after_state):
        if state and _FORBIDDEN_KEYS & state.keys():
            raise ValueError("Audit state must not contain secrets or date of birth")

    entry = AuditLog(
        family_id=family_id,
        actor_member_id=actor_member_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_state=before_state,
        after_state=after_state,
    )
    db.add(entry)
    return entry