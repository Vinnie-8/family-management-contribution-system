"""
auth_service: the business logic for feature/auth: onboarding a new
member, authenticating a login, and handling the forced first-time
password change.

Deliberately framework-free: no FastAPI imports here, no HTTPException.
Every failure is a domain exception from core/exceptions.py. The router
layer (routers/auth.py) is the only place that knows these turn into
specific HTTP responses (via main.py's exception handlers).
"""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    DuplicateMemberError,
    InactiveMemberError,
    InvalidCredentialsError,
    TempPasswordExpiredError,
)
from app.core.security import (
    create_access_token,
    generate_temp_password,
    hash_password,
    temp_password_expiry,
    verify_password,
)
from app.models.member import Member
from app.services import audit_service

_KE_PHONE = re.compile(r"^(?:\+?254|0)([17]\d{8})$")


def _normalize_identifier(identifier: str) -> str:
    """Make a typed login identifier match how it is stored:
    emails lowercased, phones as +254XXXXXXXXX."""
    identifier = identifier.strip()
    if "@" in identifier:
        return identifier.lower()
    cleaned = re.sub(r"[\s\-()]", "", identifier)
    match = _KE_PHONE.match(cleaned)
    return f"+254{match.group(1)}" if match else identifier


# --- Notification stub (FR1.3) ---
# Delivering a temp password properly belongs to feature/notifications,
# which doesn't exist yet. This stub lets onboarding be fully real and
# testable today. Swapping in a real SMS gateway later requires no
# change to any code that calls send_sms().
# Remove the print once a real gateway exists: logs must not hold credentials.
def send_sms(destination: str, message: str) -> None:
    print(f"[SMS stub] to {destination}: {message}")


def onboard_member(
    db: Session,
    *,
    family_id: uuid.UUID,
    name: str,
    is_minor: bool,
    phone_number: Optional[str] = None,
    email: Optional[str] = None,
    id_number: Optional[str] = None,
    category: Optional[str] = None,
    household_id: Optional[uuid.UUID] = None,
    actor_member_id: Optional[uuid.UUID] = None,
) -> Tuple[Member, Optional[str]]:
    """
    Creates a new Member row (FR1.1). For an adult, generates a temp
    password, hashes it, sets must_change_password=True and an expiry,
    and "delivers" it via the send_sms() stub. For a minor, no
    credentials are issued at all (FR1.7): hashed_password stays null,
    must_change_password stays False, and there is no code path here
    that ever gives a minor a password.

    Returns (member, plain_temp_password). The plain temp password is
    returned ONLY so the caller (router) can confirm what was "sent";
    it is never stored anywhere. For a minor, the second value is None.
    """
    if phone_number:
        existing = db.query(Member).filter(Member.phone_number == phone_number).first()
        if existing is not None:
            raise DuplicateMemberError(f"Phone number {phone_number} is already registered")
    if email:
        existing = db.query(Member).filter(Member.email == email).first()
        if existing is not None:
            raise DuplicateMemberError(f"Email {email} is already registered")
    if id_number:
        existing = db.query(Member).filter(Member.id_number == id_number).first()
        if existing is not None:
            raise DuplicateMemberError(f"ID Number {id_number} is already registered")

    plain_temp_password: Optional[str] = None
    hashed_password = None
    must_change_password = False
    password_expires_at = None

    if not is_minor:
        plain_temp_password = generate_temp_password()
        hashed_password = hash_password(plain_temp_password)
        must_change_password = True
        password_expires_at = temp_password_expiry()

    member = Member(
        family_id=family_id,
        household_id=household_id,
        name=name,
        id_number=id_number,
        phone_number=phone_number,
        email=email,
        category=category,
        is_minor=is_minor,
        is_active=True,
        hashed_password=hashed_password,
        must_change_password=must_change_password,
        password_expires_at=password_expires_at,
    )
    db.add(member)
    try:
        db.flush()  # assigns member.id; needed below for audit_log's entity_id
    except IntegrityError:
        # Two simultaneous requests can both pass the checks above;
        # the unique columns are the real guard.
        db.rollback()
        raise DuplicateMemberError(
            "A member with this phone, email or ID number already exists"
        )

    audit_service.log_action(
        db,
        family_id=family_id,
        actor_member_id=actor_member_id,
        action="create",
        entity_type="member",
        entity_id=member.id,
        after_state={"name": name, "is_minor": is_minor},
    )

    if not is_minor and plain_temp_password:
        destination = phone_number or email
        send_sms(
            destination,
            f"Welcome to the family system. Your temporary password is: {plain_temp_password}",
        )

    return member, plain_temp_password


def authenticate(db: Session, *, identifier: str, password: str) -> Tuple[Member, str]:
    """
    Logs a member in via phone OR email (per Decision Log) plus password.
    Returns (member, access_token).

    Deliberately generic on failure: InvalidCredentialsError is raised
    for "no such member", "no password set" AND "wrong password" alike,
    with the same message, so an attacker can't use the error to
    enumerate valid phone numbers/emails.

    Checks run in this order: member exists and password matches ->
    is_active (universal gate, FR1.6) -> temp password expiry (FR1.5).
    The password is verified first so that account status is never
    revealed to someone who doesn't know the password.

    Note: must_change_password is NOT checked here. Login succeeds either
    way; core/permissions.py's require_full_access is what restricts a
    must-change-password member to the change-password endpoint on every
    subsequent request.
    """
    identifier = _normalize_identifier(identifier)

    member = (
        db.query(Member)
        .filter((Member.phone_number == identifier) | (Member.email == identifier))
        .first()
    )
    if (
        member is None
        or member.hashed_password is None
        or not verify_password(password, member.hashed_password)
    ):
        raise InvalidCredentialsError("Invalid credentials")

    if not member.is_active:
        raise InactiveMemberError("Account is deactivated")

    if member.must_change_password and member.password_expires_at is not None:
        if datetime.now(timezone.utc) >= member.password_expires_at:
            raise TempPasswordExpiredError(
                "Temporary password expired. Request a new one from the Chairman."
            )

    access_token = create_access_token(str(member.id))
    return member, access_token


def change_password(db: Session, *, member: Member, current_password: str, new_password: str) -> None:
    """
    FR1.4: sets a permanent password, clears must_change_password and
    password_expires_at. Requires the CURRENT password even though the
    member is already authenticated via their access token: defense in
    depth against a stolen/intercepted token being used to silently lock
    the real member out.

    This function doesn't invalidate the member's current access token
    (token revocation is parked), so for now the old token remains valid
    until it naturally expires. Revisit once jti revocation is built.
    """
    if member.hashed_password is None or not verify_password(current_password, member.hashed_password):
        raise InvalidCredentialsError("Current password is incorrect")

    before = {"must_change_password": member.must_change_password}

    member.hashed_password = hash_password(new_password)
    member.must_change_password = False
    member.password_expires_at = None

    audit_service.log_action(
        db,
        family_id=member.family_id,
        actor_member_id=member.id,
        action="update",
        entity_type="member",
        entity_id=member.id,
        before_state=before,
        after_state={"must_change_password": False},
    )