"""
Expenses router. The Treasurer records expenses; the Chairman approves, rejects and
voids them; the Secretary can view.
Thin by design: validate input, call one service function, commit, shape the response.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_role
from app.database import get_db
from app.models.member import Member
from app.schemas.expenses import ExpenseActionRequest, ExpenseCreateRequest, ExpenseResponse
from app.services import expense_service

router = APIRouter()

VIEWERS = ("chairman", "secretary", "treasurer")


@router.post("", response_model=ExpenseResponse, status_code=201)
def record_expense(
    body: ExpenseCreateRequest,
    actor: Member = Depends(require_role("treasurer")),
    db: Session = Depends(get_db),
):
    expense = expense_service.record_expense(
        db,
        actor=actor,
        event_id=body.event_id,
        from_standing_fund=body.from_standing_fund,
        category=body.category,
        description=body.description,
        amount=body.amount,
        on_date=body.date,
        beneficiary_member_id=body.beneficiary_member_id,
    )
    db.commit()
    return ExpenseResponse.model_validate(expense)


@router.get("", response_model=List[ExpenseResponse])
def list_expenses(
    status: Optional[str] = None,
    event_id: Optional[uuid.UUID] = None,
    financial_year_id: Optional[uuid.UUID] = None,
    category: Optional[str] = None,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    expenses = expense_service.list_expenses(
        db, family_id=actor.family_id, status=status, event_id=event_id,
        financial_year_id=financial_year_id, category=category,
    )
    return [ExpenseResponse.model_validate(e) for e in expenses]


@router.post("/{expense_id}/approve", response_model=ExpenseResponse)
def approve_expense(
    expense_id: uuid.UUID,
    actor: Member = Depends(require_role("chairman")),
    db: Session = Depends(get_db),
):
    expense = expense_service.approve_expense(db, actor=actor, expense_id=expense_id)
    db.commit()
    return ExpenseResponse.model_validate(expense)


@router.post("/{expense_id}/reject", response_model=ExpenseResponse)
def reject_expense(
    expense_id: uuid.UUID,
    body: ExpenseActionRequest,
    actor: Member = Depends(require_role("chairman")),
    db: Session = Depends(get_db),
):
    expense = expense_service.reject_expense(
        db, actor=actor, expense_id=expense_id, reason=body.reason
    )
    db.commit()
    return ExpenseResponse.model_validate(expense)


@router.post("/{expense_id}/void", response_model=ExpenseResponse)
def void_expense(
    expense_id: uuid.UUID,
    body: ExpenseActionRequest,
    actor: Member = Depends(require_role("chairman")),
    db: Session = Depends(get_db),
):
    expense = expense_service.void_expense(
        db, actor=actor, expense_id=expense_id, reason=body.reason
    )
    db.commit()
    return ExpenseResponse.model_validate(expense)