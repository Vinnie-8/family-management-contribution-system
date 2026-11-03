"""
payment_service: recording, claiming, confirming, rejecting and voiding payments.
Framework-free: failures are domain exceptions. Services never commit.

This is the ONLY code that changes Pledge.fulfilled_amount, Fine.fulfilled_amount
and StandingFund.balance. Every change happens in one transaction, after locking
the target row, so two payments arriving together can't both squeeze past a limit.

Lock order is always: pledge or fine first, then the welfare fund. Anything that
takes both takes them in that order, so two requests can't deadlock.
"""
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import local_date, now_utc, today_local
from app.core.exceptions import BusinessRuleError, DuplicateMemberError, NotFoundError, PermissionDeniedError
from app.models.campaign import Campaign
from app.models.financial_year import FinancialYear
from app.models.fine import Fine
from app.models.member import Member
from app.models.payment import Payment
from app.models.pledge import Pledge
from app.models.standing_fund import StandingFund
from app.services import audit_service, pledge_service, standing_fund_service
from app.services.financial_year_service import find_year_for_date
from app.services.member_service import get_member_in_family


class DuplicatePaymentError(DuplicateMemberError):
    """Same HTTP 409 as a duplicate member: the existing handler covers subclasses."""


@dataclass
class Target:
    kind: str  # "pledge" | "fine" | "fund"
    member_id: uuid.UUID
    pledge: Optional[Pledge] = None
    fine: Optional[Fine] = None
    fund: Optional[StandingFund] = None


# ---------- Finding and checking the target ----------

def get_payment_in_family(
    db: Session, *, family_id: uuid.UUID, payment_id: uuid.UUID, for_update: bool = False
) -> Payment:
    query = db.query(Payment).filter(Payment.id == payment_id, Payment.family_id == family_id)
    if for_update:
        query = query.with_for_update()
    payment = query.first()
    if payment is None:
        raise NotFoundError("Payment not found")
    return payment


def _lock_fine(db: Session, *, family_id: uuid.UUID, fine_id: uuid.UUID) -> Fine:
    fine = (
        db.query(Fine)
        .filter(Fine.id == fine_id, Fine.family_id == family_id)
        .with_for_update()
        .first()
    )
    if fine is None:
        raise NotFoundError("Fine not found")
    return fine


def _resolve_target(
    db: Session,
    *,
    family_id: uuid.UUID,
    pledge_id: Optional[uuid.UUID],
    fine_id: Optional[uuid.UUID],
    to_standing_fund: bool,
    member_id: Optional[uuid.UUID],
) -> Target:
    """Finds and locks the pledge, fine or fund a payment is for."""
    if pledge_id is not None:
        pledge = pledge_service.get_pledge_in_family(
            db, family_id=family_id, pledge_id=pledge_id, for_update=True
        )
        if member_id is not None and member_id != pledge.member_id:
            raise BusinessRuleError("member_id does not match the member of this pledge")
        return Target("pledge", pledge.member_id, pledge=pledge)
    if fine_id is not None:
        fine = _lock_fine(db, family_id=family_id, fine_id=fine_id)
        if member_id is not None and member_id != fine.member_id:
            raise BusinessRuleError("member_id does not match the member who was fined")
        return Target("fine", fine.member_id, fine=fine)
    if to_standing_fund:
        if member_id is None:
            raise BusinessRuleError("A welfare-fund payment needs to say which member it counts for")
        member = get_member_in_family(db, family_id=family_id, member_id=member_id)
        fund = standing_fund_service.get_or_create_fund(db, family_id, lock=True)
        return Target("fund", member.id, fund=fund)
    raise BusinessRuleError("A payment needs a pledge, a fine, or the welfare fund as its target")


def _target_from_payment(db: Session, payment: Payment) -> Target:
    return _resolve_target(
        db,
        family_id=payment.family_id,
        pledge_id=payment.pledge_id,
        fine_id=payment.fine_id,
        to_standing_fund=payment.standing_fund_id is not None,
        member_id=payment.member_id,
    )


def _require_open_year_today(db: Session, family_id: uuid.UUID) -> None:
    """Money that isn't tied to a campaign counts toward the year it is received in."""
    year = find_year_for_date(db, family_id=family_id, on_date=today_local())
    if year is None:
        raise BusinessRuleError(
            "There is no financial year covering today's date. The Chairman must create one"
        )
    if year.status != "open":
        raise BusinessRuleError("The financial year covering today is closed")


def _check_can_receive(db: Session, target: Target, amount: Decimal) -> None:
    """Can this target accept this amount right now?"""
    if target.kind == "pledge":
        pledge = target.pledge
        if pledge.status == "cancelled":
            raise BusinessRuleError("This pledge is cancelled")
        if pledge.status == "fulfilled" or pledge.fulfilled_amount >= pledge.amount:
            raise BusinessRuleError("This pledge is already fully paid")
        campaign = db.get(Campaign, pledge.campaign_id)
        if campaign.status != "open":
            raise BusinessRuleError(f"The campaign is {campaign.status}. It no longer accepts payments")
        year = db.get(FinancialYear, campaign.financial_year_id)
        if year.status != "open":
            raise BusinessRuleError("The campaign's financial year is closed")
        remaining = pledge.amount - pledge.fulfilled_amount
        if amount > remaining:
            raise BusinessRuleError(
                f"This is more than is still owed ({remaining}). Record the surplus as a separate "
                "payment to the welfare fund"
            )
    elif target.kind == "fine":
        fine = target.fine
        if fine.status not in ("unpaid", "partial"):
            raise BusinessRuleError(f"This fine is {fine.status}. It no longer accepts payments")
        _require_open_year_today(db, fine.family_id)
        remaining = fine.amount - fine.fulfilled_amount
        if amount > remaining:
            raise BusinessRuleError(
                f"This is more than is still owed on the fine ({remaining}). "
                "Record the surplus as a separate payment to the welfare fund"
            )
    else:
        _require_open_year_today(db, target.fund.family_id)


def _change_fund(fund: StandingFund, signed_amount: Decimal) -> None:
    new_balance = fund.balance + signed_amount
    if new_balance < 0:
        raise BusinessRuleError(
            "This would take the welfare fund below zero, because that money has already been spent"
        )
    fund.balance = new_balance


def _apply(db: Session, payment: Payment, target: Target, *, sign: int) -> None:
    """Adds (sign=+1) or removes (sign=-1) a payment from the target's totals."""
    amount = payment.amount if sign > 0 else -payment.amount
    if target.kind == "pledge":
        pledge = target.pledge
        new_paid = pledge.fulfilled_amount + amount
        if new_paid < 0 or new_paid > pledge.amount:
            raise BusinessRuleError("This would put the pledge's paid amount out of range")
        pledge.fulfilled_amount = new_paid
        pledge_service.recompute_pledge_status(db, pledge)
    elif target.kind == "fine":
        fine = target.fine
        new_paid = fine.fulfilled_amount + amount
        if new_paid < 0 or new_paid > fine.amount:
            raise BusinessRuleError("This would put the fine's paid amount out of range")
        fine.fulfilled_amount = new_paid
        fine.status = "paid" if new_paid >= fine.amount else ("partial" if new_paid > 0 else "unpaid")
        # Fine money belongs to the welfare fund.
        _change_fund(standing_fund_service.lock_fund(db, fine.standing_fund_id), amount)
    else:
        _change_fund(target.fund, amount)


def _payment_year(db: Session, payment: Payment, target: Target) -> Optional[FinancialYear]:
    """The financial year a confirmed payment belongs to: a pledge payment to its
    campaign's year, any other to the year containing the day it was confirmed."""
    if target.kind == "pledge":
        campaign = db.get(Campaign, target.pledge.campaign_id)
        return db.get(FinancialYear, campaign.financial_year_id)
    return find_year_for_date(
        db, family_id=payment.family_id, on_date=local_date(payment.confirmed_at)
    )


def _state(payment: Payment) -> dict:
    return {
        "amount": str(payment.amount),
        "method": payment.method,
        "status": payment.status,
        "pledge_id": str(payment.pledge_id) if payment.pledge_id else None,
        "fine_id": str(payment.fine_id) if payment.fine_id else None,
        "standing_fund_id": str(payment.standing_fund_id) if payment.standing_fund_id else None,
    }


# ---------- Creating ----------

def _create(
    db: Session,
    *,
    actor: Member,
    target: Target,
    paid_by_id: uuid.UUID,
    method: str,
    amount: Decimal,
    item_description: Optional[str],
    mpesa_transaction_code: Optional[str],
    idempotency_key: Optional[str],
    confirmed: bool,
) -> Payment:
    if mpesa_transaction_code and db.query(Payment.id).filter(
        Payment.mpesa_transaction_code == mpesa_transaction_code
    ).first():
        raise DuplicatePaymentError("This M-Pesa transaction code has already been recorded")

    payment = Payment(
        family_id=actor.family_id,
        pledge_id=target.pledge.id if target.pledge else None,
        fine_id=target.fine.id if target.fine else None,
        standing_fund_id=target.fund.id if target.fund else None,
        member_id=target.member_id,
        paid_by=paid_by_id,
        method=method,
        amount=amount,
        item_description=item_description,
        mpesa_transaction_code=mpesa_transaction_code,
        idempotency_key=idempotency_key,
        status="confirmed" if confirmed else "pending",
        recorded_by=actor.id,
        confirmed_by=actor.id if confirmed else None,
        confirmed_at=now_utc() if confirmed else None,
    )
    db.add(payment)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        raise DuplicatePaymentError("This payment duplicates one already recorded")

    if confirmed:
        _apply(db, payment, target, sign=+1)
        db.flush()
    return payment


def _existing_by_key(db: Session, family_id: uuid.UUID, key: Optional[str]) -> Optional[Payment]:
    if not key:
        return None
    return db.query(Payment).filter(
        Payment.family_id == family_id, Payment.idempotency_key == key
    ).first()


def record_payment(
    db: Session,
    *,
    actor: Member,
    pledge_id: Optional[uuid.UUID],
    fine_id: Optional[uuid.UUID],
    to_standing_fund: bool,
    member_id: Optional[uuid.UUID],
    paid_by: Optional[uuid.UUID],
    method: str,
    amount: Decimal,
    item_description: Optional[str],
    mpesa_transaction_code: Optional[str],
    idempotency_key: Optional[str],
) -> Tuple[Payment, bool]:
    """An officer records money received. It is confirmed straight away.
    Returns (payment, created). created is False when the idempotency key was seen
    before, and the first payment is returned instead of making a second."""
    existing = _existing_by_key(db, actor.family_id, idempotency_key)
    if existing is not None:
        return existing, False

    target = _resolve_target(
        db, family_id=actor.family_id, pledge_id=pledge_id, fine_id=fine_id,
        to_standing_fund=to_standing_fund, member_id=member_id,
    )
    _check_can_receive(db, target, amount)

    payer_id = target.member_id
    if paid_by is not None:
        payer_id = get_member_in_family(db, family_id=actor.family_id, member_id=paid_by).id

    payment = _create(
        db, actor=actor, target=target, paid_by_id=payer_id, method=method, amount=amount,
        item_description=item_description, mpesa_transaction_code=mpesa_transaction_code,
        idempotency_key=idempotency_key, confirmed=True,
    )
    audit_service.log_action(
        db, family_id=actor.family_id, actor_member_id=actor.id,
        action="confirm_payment", entity_type="payment", entity_id=payment.id,
        after_state={**_state(payment), "recorded_directly": True},
    )
    return payment, True


def submit_claim(
    db: Session,
    *,
    actor: Member,
    pledge_id: Optional[uuid.UUID],
    fine_id: Optional[uuid.UUID],
    to_standing_fund: bool,
    method: str,
    amount: Decimal,
    item_description: Optional[str],
    mpesa_transaction_code: Optional[str],
    idempotency_key: Optional[str],
) -> Tuple[Payment, bool]:
    """A member says they paid. It stays pending until the Treasurer or Chairman confirms it.
    A member can claim toward their own pledges and fines, or a pledge they made for someone
    (a guardian for a minor), or give to the welfare fund."""
    existing = _existing_by_key(db, actor.family_id, idempotency_key)
    if existing is not None:
        return existing, False

    target = _resolve_target(
        db, family_id=actor.family_id, pledge_id=pledge_id, fine_id=fine_id,
        to_standing_fund=to_standing_fund, member_id=actor.id if to_standing_fund else None,
    )
    if target.kind == "pledge" and actor.id not in (target.pledge.member_id, target.pledge.pledged_by):
        raise PermissionDeniedError("You can only claim payments toward your own pledges")
    if target.kind == "fine" and target.member_id != actor.id:
        raise PermissionDeniedError("You can only claim payments toward your own fines")
    _check_can_receive(db, target, amount)

    payment = _create(
        db, actor=actor, target=target, paid_by_id=actor.id, method=method, amount=amount,
        item_description=item_description, mpesa_transaction_code=mpesa_transaction_code,
        idempotency_key=idempotency_key, confirmed=False,
    )
    audit_service.log_action(
        db, family_id=actor.family_id, actor_member_id=actor.id,
        action="create", entity_type="payment", entity_id=payment.id,
        after_state=_state(payment),
    )
    return payment, True


# ---------- Deciding on a claim, and voiding ----------

def confirm_payment(db: Session, *, actor: Member, payment_id: uuid.UUID) -> Payment:
    payment = get_payment_in_family(db, family_id=actor.family_id, payment_id=payment_id, for_update=True)
    if payment.status != "pending":
        raise BusinessRuleError(f"Only a pending claim can be confirmed. This payment is {payment.status}")
    if payment.recorded_by == actor.id:
        raise PermissionDeniedError("You can't confirm your own payment claim. Ask another officer")

    # Things may have changed since the claim was made, so check again under the lock.
    target = _target_from_payment(db, payment)
    _check_can_receive(db, target, payment.amount)

    payment.status = "confirmed"
    payment.confirmed_by = actor.id
    payment.confirmed_at = now_utc()
    _apply(db, payment, target, sign=+1)
    db.flush()
    audit_service.log_action(
        db, family_id=actor.family_id, actor_member_id=actor.id,
        action="confirm_payment", entity_type="payment", entity_id=payment.id,
        before_state={"status": "pending"}, after_state=_state(payment),
    )
    return payment


def reject_payment(db: Session, *, actor: Member, payment_id: uuid.UUID, reason: str) -> Payment:
    payment = get_payment_in_family(db, family_id=actor.family_id, payment_id=payment_id, for_update=True)
    if payment.status != "pending":
        raise BusinessRuleError(f"Only a pending claim can be rejected. This payment is {payment.status}")
    payment.status = "rejected"
    payment.reject_reason = reason
    audit_service.log_action(
        db, family_id=actor.family_id, actor_member_id=actor.id,
        action="reject_payment", entity_type="payment", entity_id=payment.id,
        before_state={"status": "pending"},
        after_state={"status": "rejected", "reason": reason},
    )
    return payment


def void_payment(db: Session, *, actor: Member, payment_id: uuid.UUID, reason: str) -> Payment:
    """Reverses a confirmed payment that was recorded by mistake. The row is kept."""
    payment = get_payment_in_family(db, family_id=actor.family_id, payment_id=payment_id, for_update=True)
    if payment.status != "confirmed":
        raise BusinessRuleError(f"Only a confirmed payment can be voided. This payment is {payment.status}")

    target = _target_from_payment(db, payment)
    year = _payment_year(db, payment, target)
    if year is None or year.status != "open":
        raise BusinessRuleError(
            "This payment belongs to a closed financial year, so it can't be changed"
        )

    _apply(db, payment, target, sign=-1)
    payment.status = "voided"
    payment.voided_by = actor.id
    payment.voided_at = now_utc()
    payment.void_reason = reason
    db.flush()
    audit_service.log_action(
        db, family_id=actor.family_id, actor_member_id=actor.id,
        action="void_payment", entity_type="payment", entity_id=payment.id,
        before_state={"status": "confirmed"},
        after_state={"status": "voided", "reason": reason, "amount": str(payment.amount)},
    )
    return payment


# ---------- Reading ----------

def member_name(db: Session, member_id: uuid.UUID) -> str:
    return db.query(Member.name).filter(Member.id == member_id).scalar()


def list_payments(
    db: Session,
    *,
    family_id: uuid.UUID,
    member_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    pledge_id: Optional[uuid.UUID] = None,
    fine_id: Optional[uuid.UUID] = None,
    limit: int = 200,
) -> List[Tuple[Payment, str]]:
    query = (
        db.query(Payment, Member.name)
        .join(Member, Member.id == Payment.member_id)
        .filter(Payment.family_id == family_id)
    )
    if member_id is not None:
        query = query.filter(Payment.member_id == member_id)
    if status is not None:
        query = query.filter(Payment.status == status)
    if pledge_id is not None:
        query = query.filter(Payment.pledge_id == pledge_id)
    if fine_id is not None:
        query = query.filter(Payment.fine_id == fine_id)
    return query.order_by(Payment.created_at.desc()).limit(limit).all()


def list_my_payments(db: Session, *, member: Member, limit: int = 200) -> List[Tuple[Payment, str]]:
    """Payments that count for me, or that I paid or claimed."""
    return (
        db.query(Payment, Member.name)
        .join(Member, Member.id == Payment.member_id)
        .filter(
            Payment.family_id == member.family_id,
            (Payment.member_id == member.id) | (Payment.paid_by == member.id),
        )
        .order_by(Payment.created_at.desc())
        .limit(limit)
        .all()
    )