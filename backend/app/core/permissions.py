"""
Authentication/authorization dependencies for FastAPI routes.

get_current_member is the single place a token resolves to a member, and the
only place is_active is checked. Everything else builds on it.
"""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.member import Member
from app.models.member_role import MemberRole
from app.models.role import Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_member(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Member:
    member_id = decode_access_token(token)
    if member_id is None:
        raise _unauthorized("Invalid or expired token")
    try:
        member_uuid = uuid.UUID(member_id)
    except ValueError:
        raise _unauthorized("Invalid or expired token")

    member = db.get(Member, member_uuid)
    if member is None:
        raise _unauthorized("Member no longer exists")

    # The universal gate: the only is_active check in the codebase.
    if not member.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    # A member who computes as a minor never has a valid session.
    if member.is_minor:
        raise _unauthorized("Invalid or expired token")

    return member


def require_role(*role_names: str):
    """require_role("chairman", "secretary") passes if the member holds at
    least one of them (union of roles)."""
    allowed = {r.lower() for r in role_names}
    if not allowed:
        raise ValueError("require_role needs at least one role name")

    def dependency(
        current_member: Member = Depends(get_current_member),
        db: Session = Depends(get_db),
    ) -> Member:
        member_role_names = {
            name.lower()
            for (name,) in (
                db.query(Role.name)
                .join(MemberRole, MemberRole.role_id == Role.id)
                .filter(MemberRole.member_id == current_member.id)
                .all()
            )
        }
        if allowed.isdisjoint(member_role_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_member

    return dependency