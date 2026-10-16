"""
Auth router: family registration, login, activation, and password change.
Thin by design: it validates input, calls one service function, commits,
and shapes the response. Business rules live in services/auth_service.py.
Member onboarding lives in routers/members.py (feature/members).
"""
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.permissions import get_current_member
from app.database import get_db
from app.models.member import Member
from app.schemas.auth import (
    ActivateRequest,
    ChangePasswordRequest,
    ChangePasswordResponse,
    RegisterFamilyRequest,
    TokenResponse,
)
from app.services import auth_service

router = APIRouter()


@router.post("/register-family", response_model=TokenResponse, status_code=201)
def register_family(body: RegisterFamilyRequest, db: Session = Depends(get_db)):
    # No auth: the registration code is the gate.
    member, access_token = auth_service.register_family(
        db,
        registration_code=body.registration_code,
        family_name=body.family_name,
        age_of_majority=body.age_of_majority,
        name=body.name,
        password=body.password,
        phone_number=body.phone_number,
        email=body.email,
        id_number=body.id_number,
    )
    db.commit()
    return TokenResponse(access_token=access_token, member_id=str(member.id), name=member.name)


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # Swagger's Authorize form sends form data; the email/phone goes in "username".
    member, access_token = auth_service.authenticate(
        db, identifier=form.username, password=form.password
    )
    db.commit()  # saves the audit row written by authenticate()
    return TokenResponse(access_token=access_token, member_id=str(member.id), name=member.name)


@router.post("/activate", response_model=TokenResponse)
def activate(body: ActivateRequest, db: Session = Depends(get_db)):
    # No auth: the activation token in the invite link is the credential.
    member, access_token = auth_service.activate_member(
        db,
        token=body.token,
        new_password=body.new_password,
        phone_number=body.phone_number,
        email=body.email,
    )
    db.commit()
    return TokenResponse(access_token=access_token, member_id=str(member.id), name=member.name)


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    body: ChangePasswordRequest,
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    auth_service.change_password(
        db,
        member=member,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    db.commit()
    return ChangePasswordResponse()