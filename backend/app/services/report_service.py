"""
report_service: read-only reports. Framework-free, and it never changes anything.

Every figure comes from the payment, fine, pledge and expense rows. The annual
report uses exactly the same rules as closing a year (financial_year_service),
so a year's report and its closing balance always agree.
"""
import uuid
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.clock import day_bounds, local_date
from app.core.exceptions import NotFoundError
from app.models.campaign import Campaign
from app.models.event import Event
from app.models.expense import Expense
from app.models.fine import Fine
from app.models.payment import Payment
from app.models.pledge import Pledge
from app.services import financial_year_service, member_service

ZERO = Decimal("0.00")


def _sum(value) -> Decimal:
    return Decimal(value or 0)


# ---------- Campaign progress ----------

def campaign_report(db: Session, *, family_id: uuid.UUID, campaign_id: uuid.UUID) -> dict:
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.family_id == family_id)
        .first()
    )
    if campaign is None:
        raise NotFoundError("Campaign not found")

    from app.models.member import Member  # local import keeps the module header short

    rows = (
        db.query(Pledge, Member.name)
        .join(Member, Member.id == Pledge.member_id)
        .filter(Pledge.campaign_id == campaign.id, Pledge.status != "cancelled")
        .all()
    )
    pledged = sum((p.amount for p, _ in rows), ZERO)
    paid = sum((p.fulfilled_amount for p, _ in rows), ZERO)
    owing = [
        {
            "member_id": p.member_id,
            "member_name": name,
            "pledged": p.amount,
            "paid": p.fulfilled_amount,
            "outstanding": p.amount - p.fulfilled_amount,
        }
        for p, name in rows
        if p.fulfilled_amount < p.amount
    ]
    owing.sort(key=lambda r: (-r["outstanding"], r["member_name"]))

    pending = _sum(
        db.query(func.sum(Payment.amount))
        .join(Pledge, Pledge.id == Payment.pledge_id)
        .filter(Pledge.campaign_id == campaign.id, Payment.status == "pending")
        .scalar()
    )
    percent = None
    if campaign.target_amount:
        percent = (paid * 100 / campaign.target_amount).quantize(Decimal("0.01"))

    return {
        "campaign": campaign,
        "pledged_total": pledged,
        "paid_total": paid,
        "outstanding_total": pledged - paid,
        "pending_claims_total": pending,
        "percent_of_target": percent,
        "pledge_count": len(rows),
        "fully_paid_count": len(rows) - len(owing),
        "still_owing": owing,
    }


# ---------- Member statement ----------

def member_statement(db: Session, *, family_id: uuid.UUID, member_id: uuid.UUID) -> dict:
    member = member_service.get_member_in_family(db, family_id=family_id, member_id=member_id)

    pledge_rows = (
        db.query(Pledge, Campaign.name, Campaign.type)
        .join(Campaign, Campaign.id == Pledge.campaign_id)
        .filter(Pledge.member_id == member.id, Pledge.status != "cancelled")
        .order_by(Campaign.start_date.desc(), Campaign.name)
        .all()
    )
    pledges = [
        {
            "pledge_id": p.id, "campaign_name": cname, "campaign_type": ctype,
            "amount": p.amount, "paid": p.fulfilled_amount,
            "outstanding": p.amount - p.fulfilled_amount, "status": p.status,
        }
        for p, cname, ctype in pledge_rows
    ]

    fine_rows = (
        db.query(Fine)
        .filter(Fine.member_id == member.id, Fine.status != "voided")
        .order_by(Fine.date.desc(), Fine.created_at.desc())
        .all()
    )
    fines = [
        {
            "fine_id": f.id, "date": f.date, "reason": f.reason, "amount": f.amount,
            "paid": f.fulfilled_amount,
            # a waived fine owes nothing
            "outstanding": ZERO if f.status == "waived" else f.amount - f.fulfilled_amount,
            "status": f.status,
        }
        for f in fine_rows
    ]

    payment_rows = (
        db.query(Payment, Campaign.name, Fine.reason)
        .outerjoin(Pledge, Pledge.id == Payment.pledge_id)
        .outerjoin(Campaign, Campaign.id == Pledge.campaign_id)
        .outerjoin(Fine, Fine.id == Payment.fine_id)
        .filter(Payment.member_id == member.id, Payment.status.in_(("pending", "confirmed")))
        .order_by(Payment.created_at.desc())
        .all()
    )
    payments: List[dict] = []
    for p, campaign_name, fine_reason in payment_rows:
        if p.pledge_id:
            purpose = f"Pledge: {campaign_name}"
        elif p.fine_id:
            purpose = f"Fine: {fine_reason}"
        else:
            purpose = "Welfare fund"
        payments.append({
            "payment_id": p.id, "when": local_date(p.confirmed_at or p.created_at),
            "purpose": purpose, "method": p.method, "amount": p.amount, "status": p.status,
        })

    totals = {
        "pledged": sum((r["amount"] for r in pledges), ZERO),
        "paid_on_pledges": sum((r["paid"] for r in pledges), ZERO),
        "fines": sum((r["amount"] for r in fines if r["status"] != "waived"), ZERO),
        "paid_on_fines": sum((r["paid"] for r in fines), ZERO),
        "total_outstanding": sum((r["outstanding"] for r in pledges + fines), ZERO),
        "total_paid": sum((r["amount"] for r in payments if r["status"] == "confirmed"), ZERO),
    }
    return {"member": member, "pledges": pledges, "fines": fines, "payments": payments, "totals": totals}


# ---------- Annual report ----------

def year_report(db: Session, *, family_id: uuid.UUID, year_id: uuid.UUID) -> dict:
    year = financial_year_service.get_year_in_family(db, family_id=family_id, year_id=year_id)
    lower, upper = day_bounds(year.start_date, year.end_date)

    by_campaign = (
        db.query(Campaign.name, func.sum(Payment.amount))
        .join(Pledge, Pledge.campaign_id == Campaign.id)
        .join(Payment, Payment.pledge_id == Pledge.id)
        .filter(Campaign.financial_year_id == year.id, Payment.status == "confirmed")
        .group_by(Campaign.name)
        .order_by(Campaign.name)
        .all()
    )
    in_year = [
        Payment.family_id == year.family_id,
        Payment.pledge_id.is_(None),
        Payment.status == "confirmed",
        Payment.confirmed_at >= lower,
        Payment.confirmed_at < upper,
    ]
    fine_income = _sum(
        db.query(func.sum(Payment.amount)).filter(*in_year, Payment.fine_id.isnot(None)).scalar()
    )
    gifts = _sum(
        db.query(func.sum(Payment.amount)).filter(*in_year, Payment.fine_id.is_(None)).scalar()
    )

    approved = [Expense.financial_year_id == year.id, Expense.status == "approved"]
    by_category = (
        db.query(Expense.category, func.sum(Expense.amount))
        .filter(*approved).group_by(Expense.category).order_by(Expense.category).all()
    )
    by_event = (
        db.query(Event.name, func.sum(Expense.amount))
        .join(Event, Event.id == Expense.event_id)
        .filter(*approved).group_by(Event.name).order_by(Event.name).all()
    )
    from_fund = _sum(
        db.query(func.sum(Expense.amount)).filter(*approved, Expense.standing_fund_id.isnot(None)).scalar()
    )
    event_lines = [(name, _sum(total)) for name, total in by_event]
    if from_fund:
        event_lines.append(("Welfare fund", from_fund))

    income, expenses = financial_year_service.compute_year_totals(db, year)
    closing = year.closing_balance if year.status == "closed" else year.opening_balance + income - expenses
    return {
        "year": year,
        "income_by_campaign": [(name, _sum(total)) for name, total in by_campaign],
        "fine_income": fine_income,
        "welfare_fund_gifts": gifts,
        "income_total": income,
        "expenses_by_category": [(cat, _sum(total)) for cat, total in by_category],
        "expenses_by_event": event_lines,
        "expenses_total": expenses,
        "closing_balance": closing,
    }