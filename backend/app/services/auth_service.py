"""
auth_service: family registration, login, activation-token issuing,
activation (first password), and password change.
Framework-free: failures are domain exceptions.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import (
    ContactRequiredError,
    DuplicateMemberError,
    InactiveMemberError,
    InvalidActivationTokenError,
    InvalidCredentialsError,
    InvalidRegistrationCodeError,
)
from app.core.normalizers import normalize_email, normalize_identifier, normalize_phone
from app.core.security import (
    activation_expiry,
    create_access_token,
    generate_token,
    hash_password,
    hash_registration_code,
    hash_token,
    verify_password,
)
from app.models.activation_token import ActivationToken
from app.models.family import Family
from app.models.household import HouseHold
from app.models.member import Member
from app.models.member_role import MemberRole
from app.models.registration_code import RegistrationCode
from app.models.role import Role
from app.services import audit_service


# Stub until feature/notifications. The token is a credential: remove the
# print once a real gateway exists.
def send_sms(destination: str, message: str) -> None:
    print(f"[SMS stub] to {destination}: {message}")


def assert_not_registered(
    db: Session, phone_number: Optional[str], email: Optional[str], id_number: Optional[str]
) -> None:
    """Friendly duplicate errors. The unique columns remain the real guard."""
    if phone_number and db.query(Member).filter(Member.phone_number == phone_number).first():
        raise DuplicateMemberError(f"Phone number {phone_number} is already registered")
    if email and db.query(Member).filter(Member.email == email).first():
        raise DuplicateMemberError(f"Email {email} is already registered")
    if id_number and db.query(Member).filter(Member.id_number == id_number).first():
        raise DuplicateMemberError(f"ID number {id_number} is already registered")


# ---------- Registration ----------

def register_family(
    db: Session,
    *,
    registration_code: str,
    family_name: str,
    age_of_majority: int,
    name: str,
    password: str,
    phone_number: Optional[str] = None,
    email: Optional[str] = None,
    id_number: Optional[str] = None,
) -> Tuple[Member, str]:
    """Creates a family, its first household, and its Chairman in ONE transaction.
    The Chairman chooses their own password, so they are logged in straight away.
    The caller commits; if anything raises, nothing is saved."""
    now = datetime.now(timezone.utc)

    code = (
        db.query(RegistrationCode)
        .filter(RegistrationCode.code_hash == hash_registration_code(registration_code))
        .with_for_update()  # two people can't use the same code at the same moment
        .first()
    )
    if code is None or code.used_at is not None or code.expires_at <= now:
        raise InvalidRegistrationCodeError("Invalid or expired registration code")

    assert_not_registered(db, phone_number, email, id_number)

    roles = db.query(Role).filter(Role.name.in_(("chairman", "member"))).all()
    if len(roles) != 2:
        raise RuntimeError("Roles are not seeded. Run: alembic upgrade head")

    family = Family(name=family_name, age_of_majority=age_of_majority)
    db.add(family)
    db.flush()

    # The household must exist before its first member (members need a household);
    # its head is set afterwards.
    household = HouseHold(family_id=family.id, name=f"{name}'s household")
    db.add(household)
    db.flush()

    member = Member(
        family_id=family.id,
        household_id=household.id,
        name=name,
        id_number=id_number,
        phone_number=phone_number,
        email=email,
        is_active=True,
        hashed_password=hash_password(password),
    )
    db.add(member)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise DuplicateMemberError("A member with this phone, email or ID number already exists")

    household.head_member_id = member.id
    for role in roles:
        db.add(MemberRole(member_id=member.id, role_id=role.id))

    code.used_at = now
    code.used_by_family_id = family.id

    audit_service.log_action(
        db,
        family_id=family.id,
        actor_member_id=member.id,
        action="register_family",
        entity_type="family",
        entity_id=family.id,
        after_state={"name": family_name, "age_of_majority": age_of_majority},
    )
    db.flush()
    return member, create_access_token(str(member.id))


# ---------- Invites ----------

def issue_activation_token(
    db: Session, *, member: Member, sent_to: str, actor_member_id: Optional[uuid.UUID]
) -> None:
    """Create a hashed, single-use token and send the invite link.
    Any earlier unused token for this member is cancelled, so a resend
    never leaves two live links. Caller commits; call after the member is flushed."""
    now = datetime.now(timezone.utc)
    db.query(ActivationToken).filter(
        ActivationToken.member_id == member.id,
        ActivationToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)  # used_at also means "cancelled"

    plain = generate_token()
    db.add(ActivationToken(
        member_id=member.id,
        token_hash=hash_token(plain),
        sent_to=sent_to,
        expires_at=activation_expiry(),
    ))
    audit_service.log_action(
        db,
        family_id=member.family_id,
        actor_member_id=actor_member_id,
        action="send_invite",
        entity_type="member",
        entity_id=member.id,
        after_state={"sent_to_type": "email" if "@" in sent_to else "phone"},
    )
    # Fragment (#), so the token stays out of server logs and referrers.
    link = f"{settings.frontend_url}/activate#token={plain}"
    send_sms(sent_to, f"You have been invited to the family system. Set your password: {link}")


# ---------- Login ----------

def authenticate(db: Session, *, identifier: str, password: str) -> Tuple[Member, str]:
    """Phone or email + password. Generic error for every credential failure.
    Order: password check -> active -> not a minor."""
    identifier = normalize_identifier(identifier)
    member = (
        db.query(Member)
        .filter((Member.phone_number == identifier) | (Member.email == identifier))
        .first()
    )
    # Always run the password check, even when no member was found, so a
    # missing account takes as long as a wrong password (see verify_password).
    password_ok = verify_password(password, member.hashed_password if member else None)
    if member is None or not password_ok:
        raise InvalidCredentialsError("Invalid credentials")
    if not member.is_active:
        raise InactiveMemberError("Account is deactivated")
    if member.is_minor:
        raise InvalidCredentialsError("Invalid credentials")

    audit_service.log_action(
        db,
        family_id=member.family_id,
        actor_member_id=member.id,
        action="login",
        entity_type="member",
        entity_id=member.id,
    )
    return member, create_access_token(str(member.id))


# ---------- Activation ----------

def activate_member(
    db: Session,
    *,
    token: str,
    new_password: str,
    phone_number: Optional[str] = None,
    email: Optional[str] = None,
) -> Tuple[Member, str]:
    """Consume an activation token, set the first password, return a login token.
    Opening the page consumes nothing; only this call does.

    A member who has a date of birth (a minor coming of age) must supply
    their own phone or email; their DOB and invite contact are then deleted."""
    now = datetime.now(timezone.utc)
    row = (
        db.query(ActivationToken)
        .filter(ActivationToken.token_hash == hash_token(token))
        .with_for_update()
        .first()
    )
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise InvalidActivationTokenError("This link is invalid or has expired")

    member = db.get(Member, row.member_id)
    if member is None or not member.is_active or member.hashed_password is not None:
        raise InvalidActivationTokenError("This link is invalid or has expired")

    if member.date_of_birth is not None:  # coming of age
        if member.is_minor:
            raise InvalidActivationTokenError("This link is invalid or has expired")
        if not (phone_number or email):
            raise ContactRequiredError("A phone number or email is required to activate")
        if phone_number:
            normalized = normalize_phone(phone_number)
            if normalized is None:
                raise ContactRequiredError("Enter a valid Kenyan phone number")
            member.phone_number = normalized
        if email:
            member.email = normalize_email(email)
        member.date_of_birth = None
        member.invite_contact = None

    member.hashed_password = hash_password(new_password)
    row.used_at = now

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise DuplicateMemberError("That phone number or email is already registered")

    audit_service.log_action(
        db,
        family_id=member.family_id,
        actor_member_id=member.id,
        action="activate_member",
        entity_type="member",
        entity_id=member.id,
        before_state={"has_password": False},
        after_state={"has_password": True},  # never the DOB
    )
    return member, create_access_token(str(member.id))


# ---------- Change password ----------

def change_password(db: Session, *, member: Member, current_password: str, new_password: str) -> None:
    """Requires the current password even with a valid token, so a stolen
    token alone can't lock the real member out. Old tokens stay valid until
    expiry (revocation is deferred)."""
    if not verify_password(current_password, member.hashed_password):
        raise InvalidCredentialsError("Current password is incorrect")
    member.hashed_password = hash_password(new_password)
    audit_service.log_action(
        db,
        family_id=member.family_id,
        actor_member_id=member.id,
        action="change_password",
        entity_type="member",
        entity_id=member.id,
    )