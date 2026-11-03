"""
Fines router. The Chairman and Secretary record and void fines; the Chairman waives them;
the Treasurer collects payment (through /payments); members see their own fines.
Thin by design: validate input, call one service function, commit, shape the response.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import get_current_member, require_role
from app.database import get_db
from app.models.member import Member
from app.schemas.fines import FineActionRequest, FineCreateRequest, FineResponse
from app.services import campaign_service, fine_service

router = APIRouter()

RECORDERS = ("chairman", "secretary")
VIEWERS = ("chairman", "secretary", "treasurer")


def _response(db: Session, fine) -> FineResponse:
    return FineResponse.from_fine(fine, campaign_service.get_member_name(db, fine.member_id))


@router.post("", response_model=FineResponse, status_code=201)
def record_fine(
    body: FineCreateRequest,
    actor: Member = Depends(require_role(*RECORDERS)),
    db: Session = Depends(get_db),
):
    fine = fine_service.record_fine(
        db,
        actor=actor,
        member_id=body.member_id,
        reason=body.reason,
        amount=body.amount,
        on_date=body.date,
    )
    db.commit()
    return _response(db, fine)


@router.get("", response_model=List[FineResponse])
def list_fines(
    member_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    financial_year_id: Optional[uuid.UUID] = None,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    rows = fine_service.list_fines(
        db, family_id=actor.family_id, member_id=member_id, status=status,
        financial_year_id=financial_year_id,
    )
    return [FineResponse.from_fine(f, name) for f, name in rows]


@router.get("/me", response_model=List[FineResponse])
def my_fines(member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    rows = fine_service.list_fines(db, family_id=member.family_id, member_id=member.id)
    return [FineResponse.from_fine(f, name) for f, name in rows]


@router.post("/{fine_id}/waive", response_model=FineResponse)
def waive_fine(
    fine_id: uuid.UUID,
    body: FineActionRequest,
    actor: Member = Depends(require_role("chairman")),
    db: Session = Depends(get_db),
):
    fine = fine_service.waive_fine(db, actor=actor, fine_id=fine_id, reason=body.reason)
    db.commit()
    return _response(db, fine)


@router.post("/{fine_id}/void", response_model=FineResponse)
def void_fine(
    fine_id: uuid.UUID,
    body: FineActionRequest,
    actor: Member = Depends(require_role(*RECORDERS)),
    db: Session = Depends(get_db),
):
    fine = fine_service.void_fine(db, actor=actor, fine_id=fine_id, reason=body.reason)
    db.commit()
    return _response(db, fine)