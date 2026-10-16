"""
household_service: creating households, naming their head, and moving members.
Framework-free: failures are domain exceptions. Services never commit.
"""
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.household import HouseHold
from app.models.member import Member
from app.services import audit_service
from app.services.member_service import get_member_in_family


def get_household_in_family(db: Session, *, family_id: uuid.UUID, household_id: uuid.UUID) -> HouseHold:
    """A household from the caller's own family, or NotFoundError."""
    household = db.get(HouseHold, household_id)
    if household is None or household.family_id != family_id:
        raise NotFoundError("Household not found")
    return household


def count_members(db: Session, household_id: uuid.UUID) -> int:
    return db.query(func.count(Member.id)).filter(Member.household_id == household_id).scalar() or 0


def create_household(
    db: Session, *, actor: Member, name: str, parent_household_id: Optional[uuid.UUID] = None
) -> HouseHold:
    if parent_household_id is not None:
        get_household_in_family(db, family_id=actor.family_id, household_id=parent_household_id)

    household = HouseHold(
        family_id=actor.family_id, name=name, parent_household_id=parent_household_id
    )
    db.add(household)
    db.flush()
    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="create",
        entity_type="household",
        entity_id=household.id,
        after_state={
            "name": name,
            "parent_household_id": str(parent_household_id) if parent_household_id else None,
        },
    )
    return household


def list_households(db: Session, *, family_id: uuid.UUID) -> List[Tuple[HouseHold, int]]:
    rows = (
        db.query(HouseHold, func.count(Member.id))
        .outerjoin(Member, Member.household_id == HouseHold.id)
        .filter(HouseHold.family_id == family_id)
        .group_by(HouseHold.id)
        .order_by(HouseHold.name)
        .all()
    )
    return [(household, count) for household, count in rows]


def set_head(db: Session, *, actor: Member, household_id: uuid.UUID, member_id: uuid.UUID) -> HouseHold:
    """A household head must be an active adult who lives in that household."""
    household = get_household_in_family(db, family_id=actor.family_id, household_id=household_id)
    member = get_member_in_family(db, family_id=actor.family_id, member_id=member_id)
    if member.household_id != household.id:
        raise BusinessRuleError("The head must be a member of this household")
    if not member.is_active or member.is_minor:
        raise BusinessRuleError("The head must be an active adult member")

    before = {"head_member_id": str(household.head_member_id) if household.head_member_id else None}
    household.head_member_id = member.id
    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="update",
        entity_type="household",
        entity_id=household.id,
        before_state=before,
        after_state={"head_member_id": str(member.id)},
    )
    return household


def move_member(db: Session, *, actor: Member, household_id: uuid.UUID, member_id: uuid.UUID) -> Member:
    """Moves a member into another household of the same family (for example after a marriage).
    Contributions belong to the member, so their financial history moves with them."""
    target = get_household_in_family(db, family_id=actor.family_id, household_id=household_id)
    member = get_member_in_family(db, family_id=actor.family_id, member_id=member_id)
    if member.household_id == target.id:
        raise BusinessRuleError("This member is already in that household")

    old_household = db.get(HouseHold, member.household_id)
    before = {"household_id": str(member.household_id)}

    # If they headed the household they are leaving, it has no head until a new one is chosen.
    if old_household is not None and old_household.head_member_id == member.id:
        old_household.head_member_id = None

    member.household_id = target.id
    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="change_household",
        entity_type="member",
        entity_id=member.id,
        before_state=before,
        after_state={"household_id": str(target.id)},
    )
    return member