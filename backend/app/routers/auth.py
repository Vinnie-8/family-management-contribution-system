"""
Auth router: onboarding, login, and forced password change.
Thin by design: it validates input, calls one service function, commits,
and shapes the response. Business rules live in services/auth_service.py.
"""
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.permissions import ( 
    get_current_member,
    require_role,
)
from app.database import get_db
from app.models.member import Member
from app.schemas.auth import ( 
    ChangePasswordRequest,
    ChangePasswordResponse,
    MemberOnboardRequest,
    MemberOnboardResponse,
    TokenResponse,
)
from app.services import auth_service

router = APIRouter()


@router.post("/members", response_model=MemberOnboardResponse, status_code=201)
def onboard_member(
    body: MemberOnboardRequest,
    chairman: Member = Depends(require_role("chairman")),
    db: Session = Depends(get_db),
):
    member, plain_temp_password = auth_service.onboard_member(
        db,
        family_id=chairman.family_id,  # from the logged-in chairman, never the body
        actor_member_id=chairman.id,
        name=body.name,
        is_minor=body.is_minor,
        phone_number=body.phone_number,
        email=body.email,
        id_number=body.id_number,
        category=body.category,
        household_id=body.household_id,
    )
    db.commit()
    return MemberOnboardResponse(
        id=str(member.id),
        name=member.name,
        is_minor=member.is_minor,
        phone_number=member.phone_number,
        email=member.email,
        temp_password_sent=plain_temp_password is not None,
    )


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
    return TokenResponse(
        access_token=access_token,
        must_change_password=member.must_change_password,
        member_id=str(member.id),
        name=member.name,
    )


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    body: ChangePasswordRequest,
    member: Member = Depends(get_current_member),  # NOT require_full_access
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