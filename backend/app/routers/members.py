"""
Members router: onboarding, reading members, invites, deactivation, and the
audited date-of-birth lookup.
Thin by design: validate input, call one service function, commit, shape the response.
Privacy rule: ordinary members see only their own record (/me). The directory
is for the officers who run the family.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.age import age_in_years
from app.core.permissions import get_current_member, require_role
from app.database import get_db
from app.models.member import Member
from app.schemas.members import (
    DateOfBirthLookupRequest,
    DateOfBirthLookupResponse,
    InviteContactRequest,
    MemberMeResponse,
    MemberOnboardRequest,
    MemberOnboardResponse,
    MemberResponse,
    MessageResponse,
)
from app.services import member_service

router = APIRouter()

OFFICERS = ("chairman", "secretary")                 # can change things
VIEWERS = ("chairman", "secretary", "treasurer")     # can see the directory


@router.get("/me", response_model=MemberMeResponse)
def read_me(member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    roles = member_service.get_role_names(db, member.id)
    return MemberMeResponse.from_member(member, roles=roles)


@router.post("", response_model=MemberOnboardResponse, status_code=201)
def onboard_member(
    body: MemberOnboardRequest,
    actor: Member = Depends(require_role(*OFFICERS)),
    db: Session = Depends(get_db),
):
    member, invite_sent = member_service.onboard_member(
        db,
        actor=actor,  # the family comes from the logged-in officer, never the body
        member_type=body.member_type,
        name=body.name,
        household_id=body.household_id,
        phone_number=body.phone_number,
        email=body.email,
        id_number=body.id_number,
        category=body.category,
        date_of_birth=body.date_of_birth,
        guardian_member_id=body.guardian_member_id,
        relationship_label=body.relationship_label,
        invite_contact=body.invite_contact,
    )
    db.commit()
    return MemberOnboardResponse.from_member(member, invite_sent=invite_sent)


@router.get("", response_model=List[MemberResponse])
def list_members(
    household_id: Optional[uuid.UUID] = None,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    members = member_service.list_members(db, family_id=actor.family_id, household_id=household_id)
    return [MemberResponse.from_member(m) for m in members]


@router.get("/{member_id}", response_model=MemberResponse)
def read_member(
    member_id: uuid.UUID,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    member = member_service.get_member_in_family(db, family_id=actor.family_id, member_id=member_id)
    return MemberResponse.from_member(member)


@router.post("/{member_id}/resend-invite", response_model=MessageResponse)
def resend_invite(
    member_id: uuid.UUID,
    actor: Member = Depends(require_role(*OFFICERS)),
    db: Session = Depends(get_db),
):
    member_service.resend_invite(db, actor=actor, member_id=member_id)
    db.commit()
    return MessageResponse(detail="Invite sent")


@router.patch("/{member_id}/invite-contact", response_model=MessageResponse)
def set_invite_contact(
    member_id: uuid.UUID,
    body: InviteContactRequest,
    actor: Member = Depends(require_role(*OFFICERS)),
    db: Session = Depends(get_db),
):
    member_service.set_invite_contact(
        db, actor=actor, member_id=member_id, invite_contact=body.invite_contact
    )
    db.commit()
    return MessageResponse(detail="Invite contact saved")


@router.post("/{member_id}/deactivate", response_model=MessageResponse)
def deactivate_member(
    member_id: uuid.UUID,
    actor: Member = Depends(require_role(*OFFICERS)),
    db: Session = Depends(get_db),
):
    member_service.deactivate_member(db, actor=actor, member_id=member_id)
    db.commit()
    return MessageResponse(detail="Member deactivated")


@router.post("/{member_id}/reactivate", response_model=MessageResponse)
def reactivate_member(
    member_id: uuid.UUID,
    actor: Member = Depends(require_role(*OFFICERS)),
    db: Session = Depends(get_db),
):
    member_service.reactivate_member(db, actor=actor, member_id=member_id)
    db.commit()
    return MessageResponse(detail="Member reactivated")


@router.post("/{member_id}/date-of-birth-lookup", response_model=DateOfBirthLookupResponse)
def lookup_date_of_birth(
    member_id: uuid.UUID,
    body: DateOfBirthLookupRequest,
    actor: Member = Depends(require_role(*OFFICERS)),
    db: Session = Depends(get_db),
):
    # POST, not GET: it writes an audit entry, and the reason travels in the body, not the URL.
    member = member_service.lookup_date_of_birth(
        db, actor=actor, member_id=member_id, reason=body.reason
    )
    db.commit()  # saves the audit entry
    dob = member.date_of_birth
    return DateOfBirthLookupResponse(
        member_id=member.id,
        name=member.name,
        date_of_birth=dob,
        age=age_in_years(dob) if dob else None,
    )