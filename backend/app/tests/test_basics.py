import pytest
from pydantic import ValidationError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.schemas.auth import MemberOnboardRequest


# --- input validation ---

def test_phone_is_normalized():
    m = MemberOnboardRequest(name="Mary", phone_number="0712 345 679")
    assert m.phone_number == "+254712345679"


def test_email_is_lowercased():
    m = MemberOnboardRequest(name="John", email="John.Doe@Gmail.com")
    assert m.email == "john.doe@gmail.com"


def test_adult_without_contact_is_rejected():
    with pytest.raises(ValidationError):
        MemberOnboardRequest(name="NoContact")


def test_minor_without_contact_is_allowed():
    assert MemberOnboardRequest(name="Kid", is_minor=True).is_minor is True


@pytest.mark.parametrize("bad_id", ["1234567", "123456789", "1234567A"])
def test_id_number_must_be_8_digits(bad_id):
    with pytest.raises(ValidationError):
        MemberOnboardRequest(name="X", phone_number="0712345679", id_number=bad_id)


# --- passwords and tokens ---

def test_password_hash_roundtrip():
    hashed = hash_password("Secret123")
    assert verify_password("Secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_roundtrip():
    assert decode_access_token(create_access_token("member-1")) == "member-1"


def test_refresh_token_is_not_accepted_as_access_token():
    assert decode_access_token(create_refresh_token("member-1")) is None


def test_garbage_token_is_rejected():
    assert decode_access_token("not.a.token") is None