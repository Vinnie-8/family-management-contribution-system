"""
reconcile_service: checks that every stored total matches the rows behind it.

Stored totals (Pledge.fulfilled_amount, Fine.fulfilled_amount, StandingFund.balance)
are only changed by payment_service and expense_service. This recomputes them from
the confirmed payments and approved expenses and reports any difference. It never
changes anything: a difference means something went wrong and a person must look.
"""
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.fine import Fine
from app.models.payment import Payment
from app.models.pledge import Pledge
from app.models.standing_fund import StandingFund

ZERO = Decimal("0.00")


def _confirmed_by(db: Session, column) -> Dict:
    rows = (
        db.query(column, func.sum(Payment.amount))
        .filter(column.isnot(None), Payment.status == "confirmed")
        .group_by(column)
        .all()
    )
    return {key: Decimal(total) for key, total in rows}


def find_differences(db: Session) -> List[dict]:
    """A list of {kind, id, family_id, stored, expected}. Empty means all is well."""
    differences: List[dict] = []

    paid_on_pledge = _confirmed_by(db, Payment.pledge_id)
    for pledge in db.query(Pledge).all():
        expected = paid_on_pledge.get(pledge.id, ZERO)
        if pledge.fulfilled_amount != expected:
            differences.append({"kind": "pledge", "id": pledge.id, "family_id": pledge.family_id,
                                "stored": pledge.fulfilled_amount, "expected": expected})

    paid_on_fine = _confirmed_by(db, Payment.fine_id)
    for fine in db.query(Fine).all():
        expected = paid_on_fine.get(fine.id, ZERO)
        if fine.fulfilled_amount != expected:
            differences.append({"kind": "fine", "id": fine.id, "family_id": fine.family_id,
                                "stored": fine.fulfilled_amount, "expected": expected})

    direct = _confirmed_by(db, Payment.standing_fund_id)
    spent = {
        key: Decimal(total)
        for key, total in db.query(Expense.standing_fund_id, func.sum(Expense.amount))
        .filter(Expense.standing_fund_id.isnot(None), Expense.status == "approved")
        .group_by(Expense.standing_fund_id).all()
    }
    from_fines = {
        key: Decimal(total)
        for key, total in db.query(Fine.standing_fund_id, func.sum(Payment.amount))
        .join(Payment, Payment.fine_id == Fine.id)
        .filter(Payment.status == "confirmed")
        .group_by(Fine.standing_fund_id).all()
    }
    for fund in db.query(StandingFund).all():
        expected = direct.get(fund.id, ZERO) + from_fines.get(fund.id, ZERO) - spent.get(fund.id, ZERO)
        if fund.balance != expected:
            differences.append({"kind": "welfare_fund", "id": fund.id, "family_id": fund.family_id,
                                "stored": fund.balance, "expected": expected})
    return differences