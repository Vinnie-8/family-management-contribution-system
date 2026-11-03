"""
Payments router. The Chairman and Treasurer record, confirm, reject and void payments;
members submit claims and see their own payments; Secretary can view.
Thin by design: validate input, call one service function, commit, shape the response.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.permissions import get_current_member, require_role
from app.database import get_db
from app.models.member import Member
from app.schemas.payments import (
    PaymentClaimRequest,
    PaymentCreateRequest,
    PaymentResponse,
    RejectPaymentRequest,
    VoidPaymentRequest,
)
from app.services import payment_service

router = APIRouter()

MONEY_OFFICERS = ("chairman", "treasurer")
VIEWERS = ("chairman", "secretary", "treasurer")


def _response(db: Session, payment) -> PaymentResponse:
    return PaymentResponse.from_payment(payment, payment_service.member_name(db, payment.member_id))


@router.post("", response_model=PaymentResponse, status_code=201)
def record_payment(
    body: PaymentCreateRequest,
    response: Response,
    actor: Member = Depends(require_role(*MONEY_OFFICERS)),
    db: Session = Depends(get_db),
):
    """Record money received. It is confirmed straight away.
    A repeat of the same idempotency_key returns the first payment with 200."""
    payment, created = payment_service.record_payment(
        db,
        actor=actor,
        pledge_id=body.pledge_id,
        fine_id=body.fine_id,
        to_standing_fund=body.to_standing_fund,
        member_id=body.member_id,
        paid_by=body.paid_by,
        method=body.method,
        amount=body.amount,
        item_description=body.item_description,
        mpesa_transaction_code=body.mpesa_transaction_code,
        idempotency_key=body.idempotency_key,
    )
    db.commit()
    if not created:
        response.status_code = 200
    return _response(db, payment)


@router.post("/claims", response_model=PaymentResponse, status_code=201)
def submit_claim(
    body: PaymentClaimRequest,
    response: Response,
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """A member says they paid. It stays pending until the Treasurer or Chairman confirms it."""
    payment, created = payment_service.submit_claim(
        db,
        actor=member,
        pledge_id=body.pledge_id,
        fine_id=body.fine_id,
        to_standing_fund=body.to_standing_fund,
        method=body.method,
        amount=body.amount,
        item_description=body.item_description,
        mpesa_transaction_code=body.mpesa_transaction_code,
        idempotency_key=body.idempotency_key,
    )
    db.commit()
    if not created:
        response.status_code = 200
    return _response(db, payment)


@router.get("", response_model=List[PaymentResponse])
def list_payments(
    member_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    pledge_id: Optional[uuid.UUID] = None,
    fine_id: Optional[uuid.UUID] = None,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    rows = payment_service.list_payments(
        db, family_id=actor.family_id, member_id=member_id, status=status,
        pledge_id=pledge_id, fine_id=fine_id,
    )
    return [PaymentResponse.from_payment(p, name) for p, name in rows]


@router.get("/me", response_model=List[PaymentResponse])
def my_payments(member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    rows = payment_service.list_my_payments(db, member=member)
    return [PaymentResponse.from_payment(p, name) for p, name in rows]


@router.post("/{payment_id}/confirm", response_model=PaymentResponse)
def confirm_payment(
    payment_id: uuid.UUID,
    actor: Member = Depends(require_role(*MONEY_OFFICERS)),
    db: Session = Depends(get_db),
):
    payment = payment_service.confirm_payment(db, actor=actor, payment_id=payment_id)
    db.commit()
    return _response(db, payment)


@router.post("/{payment_id}/reject", response_model=PaymentResponse)
def reject_payment(
    payment_id: uuid.UUID,
    body: RejectPaymentRequest,
    actor: Member = Depends(require_role(*MONEY_OFFICERS)),
    db: Session = Depends(get_db),
):
    payment = payment_service.reject_payment(
        db, actor=actor, payment_id=payment_id, reason=body.reason
    )
    db.commit()
    return _response(db, payment)


@router.post("/{payment_id}/void", response_model=PaymentResponse)
def void_payment(
    payment_id: uuid.UUID,
    body: VoidPaymentRequest,
    actor: Member = Depends(require_role(*MONEY_OFFICERS)),
    db: Session = Depends(get_db),
):
    payment = payment_service.void_payment(
        db, actor=actor, payment_id=payment_id, reason=body.reason
    )
    db.commit()
    return _response(db, payment)