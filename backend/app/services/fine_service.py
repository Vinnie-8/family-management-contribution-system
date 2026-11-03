"""
fine_service: recording, waiving and voiding fines.
Framework-free: failures are domain exceptions. Services never commit.

Fines are PAID through payment_service (payment.fine_id). This module only
creates them and closes them out. A fine belongs to the financial year whose
dates contain its date, and its money goes into the family's welfare fund.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.clock import now_utc, today_local
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.fine import Fine
from app.models.member import Member
from app.models.payment import Payment
from app.services import audit_service, standing_fund_service
from app.services.financial_year_service import find_year_for_date
from app.services.member_service import get_member_in_family


def get_fine_in_family(
    db: Session, *, family_id: uuid.UUID, fine_id: uuid.UUID, for_update: bool = False
) -> Fine:
    query = db.query(Fine).filter(Fine.id == fine_id, Fine.family_id == family_id)
    if for_update:
        query = query.with_for_update()
    fine = query.first()
    if fine is None:
        raise NotFoundError("Fine not found")
    return fine


def record_fine(
    db: Session,
    *,
    actor: Member,
    member_id: uuid.UUID,
    reason: str,
    amount: Decimal,
    on_date: Optional[date],
) -> Fine:
    member = get_member_in_family(db, family_id=actor.family_id, member_id=member_id)
    fine_date = on_date or today_local()

    year = find_year_for_date(db, family_id=actor.family_id, on_date=fine_date)
    if year is None:
        raise BusinessRuleError(
            f"No financial year covers {fine_date}. The Chairman must create one first"
        )
    if year.status != "open":
        raise BusinessRuleError(f"The financial year {year.year} is closed")

    fund = standing_fund_service.get_or_create_fund(db, actor.family_id)
    fine = Fine(
        family_id=actor.family_id,
        member_id=member.id,
        financial_year_id=year.id,
        standing_fund_id=fund.id,
        recorded_by=actor.id,
        reason=reason,
        amount=amount,
        fulfilled_amount=Decimal("0.00"),
        date=fine_date,
        status="unpaid",
    )
    db.add(fine)
    db.flush()
    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="create",
        entity_type="fine",
        entity_id=fine.id,
        after_state={
            "member_id": str(member.id),
            "amount": str(amount),
            "reason": reason,
            "date": fine_date.isoformat(),
        },
    )
    return fine


def _check_can_close_out(db: Session, fine: Fine) -> None:
    """A fine can be waived or voided only while nothing has been paid or claimed on it."""
    if fine.status not in ("unpaid", "partial"):
        raise BusinessRuleError(f"This fine is already {fine.status}")
    if fine.fulfilled_amount > 0:
        raise BusinessRuleError("Money has been paid on this fine. Void those payments first")
    if db.query(Payment.id).filter(Payment.fine_id == fine.id, Payment.status == "pending").first():
        raise BusinessRuleError("A payment claim is waiting on this fine. Reject it first")


def waive_fine(db: Session, *, actor: Member, fine_id: uuid.UUID, reason: str) -> Fine:
    """The Chairman forgives a real fine."""
    fine = get_fine_in_family(db, family_id=actor.family_id, fine_id=fine_id, for_update=True)
    _check_can_close_out(db, fine)
    before = fine.status
    fine.status = "waived"
    fine.waive_reason = reason
    audit_service.log_action(
        db, family_id=actor.family_id, actor_member_id=actor.id,
        action="waive_fine", entity_type="fine", entity_id=fine.id,
        before_state={"status": before}, after_state={"status": "waived", "reason": reason},
    )
    return fine


def void_fine(db: Session, *, actor: Member, fine_id: uuid.UUID, reason: str) -> Fine:
    """The fine was recorded by mistake. The row is kept."""
    fine = get_fine_in_family(db, family_id=actor.family_id, fine_id=fine_id, for_update=True)
    _check_can_close_out(db, fine)
    before = fine.status
    fine.status = "voided"
    fine.voided_by = actor.id
    fine.voided_at = now_utc()
    fine.void_reason = reason
    audit_service.log_action(
        db, family_id=actor.family_id, actor_member_id=actor.id,
        action="void_fine", entity_type="fine", entity_id=fine.id,
        before_state={"status": before}, after_state={"status": "voided", "reason": reason},
    )
    return fine


def list_fines(
    db: Session,
    *,
    family_id: uuid.UUID,
    member_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    financial_year_id: Optional[uuid.UUID] = None,
) -> List[Tuple[Fine, str]]:
    query = (
        db.query(Fine, Member.name)
        .join(Member, Member.id == Fine.member_id)
        .filter(Fine.family_id == family_id)
    )
    if member_id is not None:
        query = query.filter(Fine.member_id == member_id)
    if status is not None:
        query = query.filter(Fine.status == status)
    if financial_year_id is not None:
        query = query.filter(Fine.financial_year_id == financial_year_id)
    return query.order_by(Fine.date.desc(), Fine.created_at.desc()).all()