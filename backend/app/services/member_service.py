"""
member_service: onboarding members, reading them, invites, deactivation,
the audited date-of-birth lookup, and the daily coming-of-age job.
Framework-free: failures are domain exceptions. Services never commit.
"""
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.age import age_in_years
from app.core.exceptions import (
    BusinessRuleError,
    ContactRequiredError,
    DuplicateMemberError,
    NotFoundError,
    PermissionDeniedError,
)
from app.models.activation_token import ActivationToken
from app.models.family import Family
from app.models.guardian_link import GuardianLink
from app.models.household import HouseHold
from app.models.member import Member
from app.models.member_role import MemberRole
from app.models.notification import Notification
from app.models.role import Role
from app.services import audit_service
from app.services.auth_service import assert_not_registered, issue_activation_token


def get_member_in_family(db: Session, *, family_id: uuid.UUID, member_id: uuid.UUID) -> Member:
    """A member from the caller's own family, or NotFoundError.
    Another family's member gets the same error, so nothing leaks across families."""
    member = db.get(Member, member_id)
    if member is None or member.family_id != family_id:
        raise NotFoundError("Member not found")
    return member


def get_role_names(db: Session, member_id: uuid.UUID) -> List[str]:
    rows = (
        db.query(Role.name)
        .join(MemberRole, MemberRole.role_id == Role.id)
        .filter(MemberRole.member_id == member_id)
        .order_by(Role.name)
        .all()
    )
    return [name for (name,) in rows]


# ---------- Onboarding ----------

def onboard_member(
    db: Session,
    *,
    actor: Member,
    member_type: str,
    name: str,
    household_id: Optional[uuid.UUID] = None,
    phone_number: Optional[str] = None,
    email: Optional[str] = None,
    id_number: Optional[str] = None,
    category: Optional[str] = None,
    date_of_birth: Optional[date] = None,
    guardian_member_id: Optional[uuid.UUID] = None,
    relationship_label: Optional[str] = None,
    invite_contact: Optional[str] = None,
) -> Tuple[Member, bool]:
    """Creates a member in the actor's own family. Returns (member, invite_sent).

    Adult: no password yet; an activation link is sent to their phone or email.
    Minor: stores the date of birth, gets no account and no invite until they
    reach the family's age limit (see invite_members_coming_of_age).
    The family always comes from the logged-in actor, never from the request."""
    family_id = actor.family_id
    family = db.get(Family, family_id)
    is_minor = member_type == "minor"

    guardian = None
    if guardian_member_id is not None:
        guardian = get_member_in_family(db, family_id=family_id, member_id=guardian_member_id)
        if not guardian.is_active or guardian.is_minor:
            raise BusinessRuleError("A guardian must be an active adult member")
        if household_id is None:
            household_id = guardian.household_id  # a minor joins the guardian's household

    household = db.get(HouseHold, household_id) if household_id else None
    if household is None or household.family_id != family_id:
        raise NotFoundError("Household not found")

    if is_minor and age_in_years(date_of_birth) >= family.age_of_majority:
        raise BusinessRuleError(
            f"This date of birth makes them {age_in_years(date_of_birth)}, "
            f"which is at or above your family's age limit ({family.age_of_majority}). "
            "Onboard them as an adult instead."
        )

    assert_not_registered(db, phone_number, email, id_number)

    role = db.query(Role).filter(Role.name == "member").first()
    if role is None:
        raise RuntimeError("Roles are not seeded. Run: alembic upgrade head")

    member = Member(
        family_id=family_id,
        household_id=household.id,
        name=name,
        id_number=id_number,
        phone_number=phone_number,
        email=email,
        category=category,
        date_of_birth=date_of_birth if is_minor else None,
        invite_contact=invite_contact if is_minor else None,
        is_active=True,
        hashed_password=None,  # set when they activate
    )
    db.add(member)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise DuplicateMemberError("A member with this phone, email or ID number already exists")

    db.add(MemberRole(member_id=member.id, role_id=role.id))
    if guardian is not None:
        db.add(GuardianLink(
            guardian_member_id=guardian.id,
            minor_member_id=member.id,
            relationship_label=relationship_label,
        ))

    audit_service.log_action(
        db,
        family_id=family_id,
        actor_member_id=actor.id,
        action="create",
        entity_type="member",
        entity_id=member.id,
        after_state={"name": name, "member_type": member_type, "household_id": str(household.id)},
    )

    invite_sent = False
    if not is_minor:
        issue_activation_token(
            db, member=member, sent_to=phone_number or email, actor_member_id=actor.id
        )
        invite_sent = True
    return member, invite_sent


# ---------- Reading ----------

def list_members(
    db: Session, *, family_id: uuid.UUID, household_id: Optional[uuid.UUID] = None
) -> List[Member]:
    query = (
        db.query(Member)
        .options(joinedload(Member.family))  # is_minor needs the family's age limit
        .filter(Member.family_id == family_id)
    )
    if household_id is not None:
        query = query.filter(Member.household_id == household_id)
    return query.order_by(Member.name).all()


# ---------- Invites ----------

def resend_invite(db: Session, *, actor: Member, member_id: uuid.UUID) -> None:
    """Sends a fresh activation link, cancelling any earlier one."""
    member = get_member_in_family(db, family_id=actor.family_id, member_id=member_id)
    if not member.is_active or member.hashed_password is not None:
        raise BusinessRuleError("This member is deactivated or has already activated their account")
    if member.is_minor:
        raise BusinessRuleError("A minor can't be invited until they reach the family's age limit")

    sent_to = member.phone_number or member.email or member.invite_contact
    if not sent_to:
        raise ContactRequiredError("Add a contact for this member first")
    issue_activation_token(db, member=member, sent_to=sent_to, actor_member_id=actor.id)


def set_invite_contact(
    db: Session, *, actor: Member, member_id: uuid.UUID, invite_contact: str
) -> None:
    """Records (or replaces) the contact an activation link will go to when a minor comes of age."""
    member = get_member_in_family(db, family_id=actor.family_id, member_id=member_id)
    if member.date_of_birth is None or member.hashed_password is not None:
        raise BusinessRuleError("An invite contact only applies to a minor who hasn't activated yet")
    member.invite_contact = invite_contact
    audit_service.log_action(
        db,
        family_id=member.family_id,
        actor_member_id=actor.id,
        action="update",
        entity_type="member",
        entity_id=member.id,
        after_state={"invite_contact_set": True},
    )


# ---------- Deactivation ----------

def _active_chairman_count(db: Session, family_id: uuid.UUID, excluding: uuid.UUID) -> int:
    return (
        db.query(Member.id)
        .join(MemberRole, MemberRole.member_id == Member.id)
        .join(Role, Role.id == MemberRole.role_id)
        .filter(
            Member.family_id == family_id,
            Member.is_active.is_(True),
            Member.id != excluding,
            Role.name == "chairman",
        )
        .count()
    )


def deactivate_member(db: Session, *, actor: Member, member_id: uuid.UUID) -> None:
    """Blocks a member from everything at once (is_active is the universal gate).
    Members are deactivated, never deleted, so their history stays intact."""
    member = get_member_in_family(db, family_id=actor.family_id, member_id=member_id)
    if member.id == actor.id:
        raise BusinessRuleError("You can't deactivate yourself")
    if not member.is_active:
        raise BusinessRuleError("This member is already deactivated")

    target_roles = get_role_names(db, member.id)
    if "chairman" in target_roles:
        if "chairman" not in get_role_names(db, actor.id):
            raise PermissionDeniedError("Only a chairman can deactivate a chairman")
        if _active_chairman_count(db, member.family_id, excluding=member.id) == 0:
            raise BusinessRuleError("The family needs at least one active chairman")

    member.is_active = False
    audit_service.log_action(
        db,
        family_id=member.family_id,
        actor_member_id=actor.id,
        action="deactivate_member",
        entity_type="member",
        entity_id=member.id,
        before_state={"is_active": True},
        after_state={"is_active": False},
    )


def reactivate_member(db: Session, *, actor: Member, member_id: uuid.UUID) -> None:
    member = get_member_in_family(db, family_id=actor.family_id, member_id=member_id)
    if member.is_active:
        raise BusinessRuleError("This member is already active")
    member.is_active = True
    audit_service.log_action(
        db,
        family_id=member.family_id,
        actor_member_id=actor.id,
        action="update",
        entity_type="member",
        entity_id=member.id,
        before_state={"is_active": False},
        after_state={"is_active": True},
    )


# ---------- Date of birth (private) ----------

def lookup_date_of_birth(
    db: Session, *, actor: Member, member_id: uuid.UUID, reason: str
) -> Member:
    """The only way an officer can see a date of birth. Every lookup is audited
    with who looked, at whom, and why. The date itself is never copied into the log."""
    member = get_member_in_family(db, family_id=actor.family_id, member_id=member_id)
    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="view_date_of_birth",
        entity_type="member",
        entity_id=member.id,
        after_state={"reason": reason},
    )
    return member


# ---------- Daily coming-of-age job ----------

def _notify_officers_needs_contact(db: Session, member: Member) -> int:
    """Tells the family's active Chairman and Secretary that this member needs a
    contact before they can be invited. Skips anyone already told. Returns how many were added."""
    officers = (
        db.query(Member)
        .join(MemberRole, MemberRole.member_id == Member.id)
        .join(Role, Role.id == MemberRole.role_id)
        .filter(
            Member.family_id == member.family_id,
            Member.is_active.is_(True),
            Role.name.in_(("chairman", "secretary")),
        )
        .distinct()
        .all()
    )
    message = (
        f"{member.name} has reached the family's age limit and needs a phone number or email "
        "before they can be invited. Add a contact, then resend the invite."
    )
    added = 0
    for officer in officers:
        already = (
            db.query(Notification.id)
            .filter(
                Notification.recipient_member_id == officer.id,
                Notification.type == "member_needs_contact",
                Notification.message == message,
            )
            .first()
        )
        if already is None:
            db.add(Notification(
                recipient_member_id=officer.id,
                type="member_needs_contact",
                channel="in_app",
                message=message,
            ))
            added += 1
    return added


def invite_members_coming_of_age(db: Session) -> dict:
    """Run once a day. For every minor who has reached their family's age limit
    and has no account yet: send the activation link to their invite contact, or,
    if there is none, tell the Chairman and Secretary to add one.
    The caller commits."""
    now = datetime.now(timezone.utc)
    candidates = (
        db.query(Member)
        .options(joinedload(Member.family))
        .filter(
            Member.date_of_birth.is_not(None),
            Member.hashed_password.is_(None),
            Member.is_active.is_(True),
        )
        .all()
    )
    invited = notified = already_invited = 0
    for member in candidates:
        if member.is_minor:
            continue  # not old enough yet
        live_token = (
            db.query(ActivationToken.id)
            .filter(
                ActivationToken.member_id == member.id,
                ActivationToken.used_at.is_(None),
                ActivationToken.expires_at > now,
            )
            .first()
        )
        if live_token is not None:
            already_invited += 1
            continue
        if member.invite_contact:
            issue_activation_token(
                db, member=member, sent_to=member.invite_contact, actor_member_id=None
            )
            invited += 1
        else:
            notified += _notify_officers_needs_contact(db, member)
    return {"invited": invited, "officers_notified": notified, "already_invited": already_invited}