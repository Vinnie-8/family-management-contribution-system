"""
Authentication/authorization dependencies for FastAPI routes.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.member import Member
from app.models.member_role import MemberRole
from app.models.role import Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_member(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Member:
    member_id = decode_access_token(token)
    if member_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    member = db.query(Member).filter(Member.id == member_id).first()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Member no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # The universal gate
    if not member.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    return member


def require_full_access(current_member: Member = Depends(get_current_member)) -> Member:
    """
    Blocks everything except the change-password endpoint until a member
    has replaced their temporary password (FR1.4). Apply this (instead of
    get_current_member directly) to every route EXCEPT /auth/change-password.
    """
    if current_member.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required before continuing",
        )
    return current_member


def require_role(*role_names: str):
    """
    Dependency factory: require_role("chairman", "secretary") allows either.
    """
    allowed = {r.lower() for r in role_names}
    if not allowed:
        raise ValueError("require_role needs at least one role name")

    def dependency(
        current_member: Member = Depends(require_full_access),
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