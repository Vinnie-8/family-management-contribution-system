"""
Password hashing, temporary-password generation, and JWT create/verify.
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def generate_temp_password() -> str:
    """
    Generates a random temporary password for newly onboarded members.
    we are using secrets because it is safe and unpredictable  unlike random
    """

    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(settings.temp_password_length))


def temp_password_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=settings.temp_password_expire_hours)


def _create_token(member_id: str, token_type: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": member_id,
        "type": token_type,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(member_id: str) -> str:
    return _create_token(
        member_id, "access", timedelta(minutes=settings.access_token_expire_minutes)
    )


def create_refresh_token(member_id: str) -> str:
    return _create_token(
        member_id, "refresh", timedelta(days=settings.refresh_token_expire_days)
    )

def _decode_token(token: str, expected_type: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload.get("sub")

def decode_access_token(token: str) -> Optional[str]:
    """Returns the member_id from a valid access token, or None if invalid/expired/wrong type."""
    return _decode_token(token, "access")


def decode_refresh_token(token: str) -> Optional[str]:
    """Returns the member_id from a valid refresh token, or None if invalid/expired/wrong type."""
    return _decode_token(token, "refresh")