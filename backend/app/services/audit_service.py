"""
audit_service — the single place every other service writes to AuditLog
(FR14.1). No service should ever construct an AuditLog(...) row directly;
calling log_action() here keeps the shape consistent across all 13
feature branches, and gives us one place to extend later (e.g. adding
request-IP capture) without touching every caller.
"""
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


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
    """
    Writes one immutable audit entry. Does NOT commit — the caller's
    request is still inside get_db()'s single transaction, so this entry
    commits together with whatever else the request did (e.g. the Member
    row being created), per the "one transaction" discipline in
    Security & Privacy.

    actor_member_id is optional: some actions are system-initiated
    (e.g. a campaign auto-closing at end_date) rather than performed by
    a logged-in member.

    Keyword-only arguments (the `*`) are deliberate — with 7 parameters,
    positional calls would be too easy to get wrong (swap entity_id and
    actor_member_id, both UUIDs, and nothing would catch it at the type
    level). Forcing keywords makes every call self-documenting.
    """
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
    