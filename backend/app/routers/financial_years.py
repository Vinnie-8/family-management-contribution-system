"""
Financial years router. The Chairman creates years; the Chairman, Secretary
and Treasurer can view them.
Thin by design: validate input, call one service function, commit, shape the response.
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_role
from app.database import get_db
from app.models.member import Member
from app.schemas.financial_years import FinancialYearCreateRequest, FinancialYearResponse
from app.services import financial_year_service

router = APIRouter()

VIEWERS = ("chairman", "secretary", "treasurer")


@router.post("", response_model=FinancialYearResponse, status_code=201)
def create_financial_year(
    body: FinancialYearCreateRequest,
    actor: Member = Depends(require_role("chairman")),
    db: Session = Depends(get_db),
):
    year = financial_year_service.create_year(
        db,
        actor=actor,
        year=body.year,
        start_date=body.start_date,
        end_date=body.end_date,
        opening_balance=body.opening_balance,
    )
    db.commit()
    return FinancialYearResponse.model_validate(year)


@router.get("", response_model=List[FinancialYearResponse])
def list_financial_years(
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    years = financial_year_service.list_years(db, family_id=actor.family_id)
    return [FinancialYearResponse.model_validate(y) for y in years]


@router.get("/{year_id}", response_model=FinancialYearResponse)
def read_financial_year(
    year_id: uuid.UUID,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    year = financial_year_service.get_year_in_family(db, family_id=actor.family_id, year_id=year_id)
    return FinancialYearResponse.model_validate(year)