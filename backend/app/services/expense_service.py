"""
expense_service: recording, approving, rejecting and voiding expenses.
Framework-free: failures are domain exceptions. Services never commit.

An expense is money OUT, from exactly one source: an event, or the welfare fund.
The Treasurer records it (pending); the Chairman approves it. Only an approved
expense counts. Approving a welfare-fund expense lowers the fund, and is blocked
if the fund can't cover it. The approver must be someone other than the recorder.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.clock import now_utc, today_local
from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.models.expense import Expense
from app.models.financial_year import FinancialYear
from app.models.member import Member
from app.services import audit_service, standing_fund_service
from app.services.event_service import get_event_in_family
from app.services.financial_year_service import find_year_for_date
from app.services.member_service import get_member_in_family


def get_expense_in_family(
    db: Session, *, family_id: uuid.UUID, expense_id: uuid.UUID, for_update: bool = False
) -> Expense:
    query = db.query(Expense).filter(Expense.id == expense_id, Expense.family_id == family_id)
    if for_update:
        query = query.with_for_update()
    expense = query.first()
    if expense is None:
        raise NotFoundError("Expense not found")
    return expense


def _state(expense: Expense) -> dict:
    return {
        "amount": str(expense.amount),
        "category": expense.category,
        "status": expense.status,
        "event_id": str(expense.event_id) if expense.event_id else None,
        "standing_fund_id": str(expense.standing_fund_id) if expense.standing_fund_id else None,
    }


def record_expense(
    db: Session,
    *,
    actor: Member,
    event_id: Optional[uuid.UUID],
    from_standing_fund: bool,
    category: str,
    description: Optional[str],
    amount: Decimal,
    on_date: Optional[date],
    beneficiary_member_id: Optional[uuid.UUID],
) -> Expense:
    expense_date = on_date or today_local()

    year = find_year_for_date(db, family_id=actor.family_id, on_date=expense_date)
    if year is None:
        raise BusinessRuleError(
            f"No financial year covers {expense_date}. The Chairman must create one first"
        )
    if year.status != "open":
        raise BusinessRuleError(f"The financial year {year.year} is closed")

    fund_id = None
    if event_id is not None:
        event = get_event_in_family(db, family_id=actor.family_id, event_id=event_id)
        if event.status == "closed":
            raise BusinessRuleError("This event is closed. It takes no new expenses")
    else:
        fund_id = standing_fund_service.get_or_create_fund(db, actor.family_id).id

    if beneficiary_member_id is not None:
        get_member_in_family(db, family_id=actor.family_id, member_id=beneficiary_member_id)

    expense = Expense(
        family_id=actor.family_id,
        financial_year_id=year.id,
        event_id=event_id,
        standing_fund_id=fund_id,
        beneficiary_member_id=beneficiary_member_id,
        category=category,
        description=description,
        amount=amount,
        date=expense_date,
        status="pending",
        recorded_by=actor.id,
    )
    db.add(expense)
    db.flush()
    audit_service.log_action(
        db, family_id=actor.family_id, actor_member_id=actor.id,
        action="create", entity_type="expense", entity_id=expense.id,
        after_state=_state(expense),
    )
    return expense


def approve_expense(db: Session, *, actor: Member, expense_id: uuid.UUID) -> Expense:
    expense = get_expense_in_family(db, family_id=actor.family_id, expense_id=expense_id, for_update=True)
    if expense.status != "pending":
        raise BusinessRuleError(f"Only a pending expense can be approved. This one is {expense.status}")
    if expense.recorded_by == actor.id:
        raise PermissionDeniedError(
            "You can't approve an expense you recorded yourself. Another chairman must approve it"
        )
    year = db.get(FinancialYear, expense.financial_year_id)
    if year.status != "open":
        raise BusinessRuleError(f"The financial year {year.year} is closed")

    if expense.standing_fund_id is not None:
        fund = standing_fund_service.lock_fund(db, expense.standing_fund_id)
        if fund.balance < expense.amount:
            raise BusinessRuleError(
                f"The welfare fund holds {fund.balance}, which can't cover {expense.amount}. "
                "Correct the amount, or record the missing money first"
            )
        fund.balance = fund.balance - expense.amount

    expense.status = "approved"
    expense.approved_by = actor.id
    expense.approved_at = now_utc()
    db.flush()
    audit_service.log_action(
        db, family_id=actor.family_id, actor_member_id=actor.id,
        action="approve_expense", entity_type="expense", entity_id=expense.id,
        before_state={"status": "pending"}, after_state=_state(expense),
    )
    return expense


def reject_expense(db: Session, *, actor: Member, expense_id: uuid.UUID, reason: str) -> Expense:
    expense = get_expense_in_family(db, family_id=actor.family_id, expense_id=expense_id, for_update=True)
    if expense.status != "pending":
        raise BusinessRuleError(f"Only a pending expense can be rejected. This one is {expense.status}")
    expense.status = "rejected"
    expense.reject_reason = reason
    audit_service.log_action(
        db, family_id=actor.family_id, actor_member_id=actor.id,
        action="reject_expense", entity_type="expense", entity_id=expense.id,
        before_state={"status": "pending"}, after_state={"status": "rejected", "reason": reason},
    )
    return expense


def void_expense(db: Session, *, actor: Member, expense_id: uuid.UUID, reason: str) -> Expense:
    """Reverses an approved expense recorded by mistake. The row is kept."""
    expense = get_expense_in_family(db, family_id=actor.family_id, expense_id=expense_id, for_update=True)
    if expense.status != "approved":
        raise BusinessRuleError(f"Only an approved expense can be voided. This one is {expense.status}")
    year = db.get(FinancialYear, expense.financial_year_id)
    if year.status != "open":
        raise BusinessRuleError("This expense belongs to a closed financial year, so it can't be changed")

    if expense.standing_fund_id is not None:
        fund = standing_fund_service.lock_fund(db, expense.standing_fund_id)
        fund.balance = fund.balance + expense.amount  # the money goes back

    expense.status = "voided"
    expense.voided_by = actor.id
    expense.voided_at = now_utc()
    expense.void_reason = reason
    db.flush()
    audit_service.log_action(
        db, family_id=actor.family_id, actor_member_id=actor.id,
        action="void_expense", entity_type="expense", entity_id=expense.id,
        before_state={"status": "approved"},
        after_state={"status": "voided", "reason": reason, "amount": str(expense.amount)},
    )
    return expense


def list_expenses(
    db: Session,
    *,
    family_id: uuid.UUID,
    status: Optional[str] = None,
    event_id: Optional[uuid.UUID] = None,
    financial_year_id: Optional[uuid.UUID] = None,
    category: Optional[str] = None,
) -> List[Expense]:
    query = db.query(Expense).filter(Expense.family_id == family_id)
    if status is not None:
        query = query.filter(Expense.status == status)
    if event_id is not None:
        query = query.filter(Expense.event_id == event_id)
    if financial_year_id is not None:
        query = query.filter(Expense.financial_year_id == financial_year_id)
    if category is not None:
        query = query.filter(Expense.category == category)
    return query.order_by(Expense.date.desc(), Expense.created_at.desc()).all()