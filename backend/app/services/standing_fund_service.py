"""
standing_fund_service: the family's welfare fund.
Framework-free: failures are domain exceptions. Services never commit.

There is one fund per family, created the first time it is needed. Its balance
is changed only by payment_service (money in) and expense_service (money out).
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.fine import Fine
from app.models.payment import Payment
from app.models.standing_fund import StandingFund


def get_or_create_fund(db: Session, family_id: uuid.UUID, *, lock: bool = False) -> StandingFund:
    """The family's welfare fund, created if it doesn't exist yet.
    lock=True takes a row lock, which anything that changes the balance must do."""
    query = db.query(StandingFund).filter(StandingFund.family_id == family_id)
    if lock:
        query = query.with_for_update()
    fund = query.first()
    if fund is None:
        try:
            with db.begin_nested():  # savepoint: two requests creating it at once is fine
                fund = StandingFund(family_id=family_id, name="Welfare Fund", balance=Decimal("0.00"))
                db.add(fund)
                db.flush()
        except IntegrityError:
            fund = query.first()
    return fund


def lock_fund(db: Session, fund_id: uuid.UUID) -> StandingFund:
    return db.query(StandingFund).filter(StandingFund.id == fund_id).with_for_update().one()


def recent_movements(db: Session, fund: StandingFund, limit: int = 20) -> List[Tuple[datetime, str, str, Decimal, uuid.UUID]]:
    """Newest first: (when, kind, description, signed amount, id). Voided and rejected items are left out."""
    items: List[Tuple[datetime, str, str, Decimal, uuid.UUID]] = []

    direct = (
        db.query(Payment)
        .filter(Payment.standing_fund_id == fund.id, Payment.status == "confirmed")
        .order_by(Payment.confirmed_at.desc())
        .limit(limit)
        .all()
    )
    for p in direct:
        items.append((p.confirmed_at, "payment", f"Payment ({p.method})", p.amount, p.id))

    fine_rows = (
        db.query(Payment, Fine.reason)
        .join(Fine, Fine.id == Payment.fine_id)
        .filter(Fine.standing_fund_id == fund.id, Payment.status == "confirmed")
        .order_by(Payment.confirmed_at.desc())
        .limit(limit)
        .all()
    )
    for p, reason in fine_rows:
        items.append((p.confirmed_at, "fine_payment", f"Fine paid: {reason}", p.amount, p.id))

    expenses = (
        db.query(Expense)
        .filter(Expense.standing_fund_id == fund.id, Expense.status == "approved")
        .order_by(Expense.approved_at.desc())
        .limit(limit)
        .all()
    )
    for e in expenses:
        label = e.description or e.category
        items.append((e.approved_at, "expense", f"Expense: {label}", -e.amount, e.id))

    items.sort(key=lambda row: row[0], reverse=True)
    return items[:limit]