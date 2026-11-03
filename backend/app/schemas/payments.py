"""Request/response schemas for payments."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import empty_to_none
from app.schemas.money import Money
from app.schemas.reasons import Reason

Method = Literal["cash", "bank_transfer", "mpesa", "in_kind"]


class PaymentBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # Exactly one target: a pledge, a fine, or the welfare fund.
    pledge_id: Optional[uuid.UUID] = None
    fine_id: Optional[uuid.UUID] = None
    to_standing_fund: bool = False

    method: Method
    amount: Money = Field(description="The KES value. For in_kind, the value of the item")
    item_description: Optional[str] = Field(default=None, max_length=200)  # in_kind only
    mpesa_transaction_code: Optional[str] = Field(default=None, max_length=30)  # mpesa only
    # Send the same key on a retry and you get the first payment back, not a second one.
    idempotency_key: Optional[str] = Field(default=None, max_length=100)

    @field_validator(
        "pledge_id", "fine_id", "item_description", "mpesa_transaction_code", "idempotency_key",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, v):
        return empty_to_none(v)

    @field_validator("mpesa_transaction_code")
    @classmethod
    def upper_code(cls, v):
        return None if v is None else v.upper()

    @model_validator(mode="after")
    def check_target_and_method(self):
        targets = [self.pledge_id is not None, self.fine_id is not None, self.to_standing_fund]
        if sum(targets) != 1:
            raise ValueError("Give exactly one of pledge_id, fine_id, or to_standing_fund: true")
        if self.method == "mpesa" and not self.mpesa_transaction_code:
            raise ValueError("An M-Pesa payment needs mpesa_transaction_code")
        if self.method != "mpesa" and self.mpesa_transaction_code:
            raise ValueError("mpesa_transaction_code only applies to an M-Pesa payment")
        if self.method == "in_kind" and not self.item_description:
            raise ValueError("An in-kind payment needs item_description")
        if self.method != "in_kind" and self.item_description:
            raise ValueError("item_description only applies to an in-kind payment")
        return self


class PaymentCreateRequest(PaymentBase):
    """An officer records a payment. It is confirmed straight away."""
    # Who it counts for. Needed only for a welfare-fund payment. For a pledge or fine it is
    # taken from the pledge or fine.
    member_id: Optional[uuid.UUID] = None
    # Who actually paid, if not that member (a parent for a child).
    paid_by: Optional[uuid.UUID] = None

    @field_validator("member_id", "paid_by", mode="before")
    @classmethod
    def blank_ids_to_none(cls, v):
        return empty_to_none(v)

    @model_validator(mode="after")
    def fund_needs_member(self):
        if self.to_standing_fund and self.member_id is None:
            raise ValueError("A welfare-fund payment needs member_id (who it counts for)")
        return self


class PaymentClaimRequest(PaymentBase):
    """A member says they paid. It stays pending until the Treasurer or Chairman confirms it."""


class RejectPaymentRequest(BaseModel):
    reason: Reason


class VoidPaymentRequest(BaseModel):
    reason: Reason


class PaymentResponse(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    member_name: str
    paid_by: uuid.UUID
    pledge_id: Optional[uuid.UUID] = None
    fine_id: Optional[uuid.UUID] = None
    standing_fund_id: Optional[uuid.UUID] = None
    method: str
    amount: Decimal
    item_description: Optional[str] = None
    mpesa_transaction_code: Optional[str] = None
    status: str
    recorded_by: uuid.UUID
    confirmed_by: Optional[uuid.UUID] = None
    confirmed_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
    void_reason: Optional[str] = None
    created_at: datetime

    @classmethod
    def from_payment(cls, p, member_name: str):
        return cls(
            id=p.id,
            member_id=p.member_id,
            member_name=member_name,
            paid_by=p.paid_by,
            pledge_id=p.pledge_id,
            fine_id=p.fine_id,
            standing_fund_id=p.standing_fund_id,
            method=p.method,
            amount=p.amount,
            item_description=p.item_description,
            mpesa_transaction_code=p.mpesa_transaction_code,
            status=p.status,
            recorded_by=p.recorded_by,
            confirmed_by=p.confirmed_by,
            confirmed_at=p.confirmed_at,
            reject_reason=p.reject_reason,
            void_reason=p.void_reason,
            created_at=p.created_at,
        )