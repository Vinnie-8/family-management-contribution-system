"""
Households router. Chairman and Secretary manage households; the Treasurer can view them.
Thin by design: validate input, call one service function, commit, shape the response.
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_role
from app.database import get_db
from app.models.member import Member
from app.schemas.households import (
    AddMemberRequest,
    HouseholdCreateRequest,
    HouseholdResponse,
    SetHeadRequest,
)
from app.schemas.members import MessageResponse
from app.services import household_service

router = APIRouter()

OFFICERS = ("chairman", "secretary")
VIEWERS = ("chairman", "secretary", "treasurer")


@router.post("", response_model=HouseholdResponse, status_code=201)
def create_household(
    body: HouseholdCreateRequest,
    actor: Member = Depends(require_role(*OFFICERS)),
    db: Session = Depends(get_db),
):
    household = household_service.create_household(
        db, actor=actor, name=body.name, parent_household_id=body.parent_household_id
    )
    db.commit()
    return HouseholdResponse.from_household(household, household_service.count_members(db, household.id))


@router.get("", response_model=List[HouseholdResponse])
def list_households(
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    rows = household_service.list_households(db, family_id=actor.family_id)
    return [HouseholdResponse.from_household(h, count) for h, count in rows]


@router.get("/{household_id}", response_model=HouseholdResponse)
def read_household(
    household_id: uuid.UUID,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    household = household_service.get_household_in_family(
        db, family_id=actor.family_id, household_id=household_id
    )
    return HouseholdResponse.from_household(household, household_service.count_members(db, household.id))


@router.patch("/{household_id}/head", response_model=HouseholdResponse)
def set_head(
    household_id: uuid.UUID,
    body: SetHeadRequest,
    actor: Member = Depends(require_role(*OFFICERS)),
    db: Session = Depends(get_db),
):
    household = household_service.set_head(
        db, actor=actor, household_id=household_id, member_id=body.member_id
    )
    db.commit()
    return HouseholdResponse.from_household(household, household_service.count_members(db, household.id))


@router.post("/{household_id}/members", response_model=MessageResponse)
def move_member(
    household_id: uuid.UUID,
    body: AddMemberRequest,
    actor: Member = Depends(require_role(*OFFICERS)),
    db: Session = Depends(get_db),
):
    household_service.move_member(
        db, actor=actor, household_id=household_id, member_id=body.member_id
    )
    db.commit()
    return MessageResponse(detail="Member moved")