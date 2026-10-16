"""
Security primitives: password hashing, one-time tokens/codes, and JWTs.

No database and no FastAPI in here, so services and the daily job can reuse it.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt only reads the first 72 bytes. Refuse longer input instead of
# silently truncating it.
_BCRYPT_MAX_BYTES = 72

# A real bcrypt hash of a throwaway string. verify_password() checks against it
# when there is no real hash, so "no such member" and "wrong password" take the
# same time and an attacker can't use timing to find which accounts exist.
_DUMMY_HASH = pwd_context.hash("dummy-password-for-timing-only")

# No 0/O or 1/I/L, so codes are readable on a small phone screen.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


# ---------- Passwords ----------

def hash_password(plain_password: str) -> str:
    if len(plain_password.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        raise ValueError("Password is too long (max 72 bytes).")
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """False for unactivated members (no hash) and for any bad input."""
    if len(plain_password.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        return False
    if not hashed_password:
        pwd_context.verify(plain_password, _DUMMY_HASH)  # burn the same time as a real check
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        return False


# ---------- One-time tokens and codes ----------

def generate_token() -> str:
    """Activation token: 32 random bytes, URL-safe. Store only hash_token()."""
    return secrets.token_urlsafe(32)


def generate_registration_code(length: int = 12) -> str:
    """Registration code like 'K7MQ-R2XD-9PTA'. Store only hash_registration_code()."""
    chars = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
    return "-".join(chars[i:i + 4] for i in range(0, length, 4))


def hash_token(value: str) -> str:
    """SHA-256 hex (64 chars), matching the token_hash column.

    The value is hashed exactly as given (after trimming spaces). No salt is
    needed: the input is 32 random bytes, so there is nothing to guess.
    """
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def hash_registration_code(code: str) -> str:
    """Same hash, but first forgives typing: any case, with or without dashes."""
    return hash_token(code.strip().replace("-", "").upper())


def activation_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=settings.activation_token_expire_hours)


# ---------- JWTs ----------

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
    """Member id from a valid access token, or None if invalid/expired/wrong type."""
    return _decode_token(token, "access")


def decode_refresh_token(token: str) -> Optional[str]:
    """Member id from a valid refresh token, or None if invalid/expired/wrong type."""
    return _decode_token(token, "refresh")