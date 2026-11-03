"""Welfare fund router: the balance and recent movements. Officers only."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_role
from app.database import get_db
from app.models.member import Member
from app.schemas.standing_fund import MovementResponse, StandingFundResponse
from app.services import standing_fund_service

router = APIRouter()

VIEWERS = ("chairman", "secretary", "treasurer")


@router.get("", response_model=StandingFundResponse)
def read_standing_fund(
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    fund = standing_fund_service.get_or_create_fund(db, actor.family_id)
    movements = standing_fund_service.recent_movements(db, fund)
    db.commit()  # saves the fund if this request had to create it
    return StandingFundResponse(
        id=fund.id,
        name=fund.name,
        balance=fund.balance,
        movements=[
            MovementResponse(when=when, kind=kind, description=desc, amount=amount, reference_id=ref)
            for when, kind, desc, amount, ref in movements
        ],
    )