"""Response schemas for reports. Everything here is read-only."""
import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


# ---------- Campaign progress ----------

class OwingMember(BaseModel):
    member_id: uuid.UUID
    member_name: str
    pledged: Decimal
    paid: Decimal
    outstanding: Decimal


class CampaignReportResponse(BaseModel):
    campaign_id: uuid.UUID
    name: str
    type: str
    status: str
    target_amount: Optional[Decimal] = None
    pledged_total: Decimal          # what members owe or promised (cancelled pledges left out)
    paid_total: Decimal             # confirmed money received
    outstanding_total: Decimal      # pledged_total - paid_total
    pending_claims_total: Decimal   # claimed but not yet confirmed, not counted as paid
    percent_of_target: Optional[Decimal] = None   # paid_total / target, when there is a target
    pledge_count: int
    fully_paid_count: int
    still_owing: List[OwingMember]  # biggest balance first


# ---------- Member statement ----------

class StatementPledge(BaseModel):
    pledge_id: uuid.UUID
    campaign_name: str
    campaign_type: str
    amount: Decimal
    paid: Decimal
    outstanding: Decimal
    status: str


class StatementFine(BaseModel):
    fine_id: uuid.UUID
    date: date
    reason: str
    amount: Decimal
    paid: Decimal
    outstanding: Decimal
    status: str


class StatementPayment(BaseModel):
    payment_id: uuid.UUID
    when: date
    purpose: str            # "Pledge: Burial fund", "Fine: Late", or "Welfare fund"
    method: str
    amount: Decimal
    status: str


class StatementTotals(BaseModel):
    pledged: Decimal
    paid_on_pledges: Decimal
    fines: Decimal
    paid_on_fines: Decimal
    total_outstanding: Decimal      # pledges + fines still owed
    total_paid: Decimal             # every confirmed payment, including welfare fund gifts


class MemberStatementResponse(BaseModel):
    member_id: uuid.UUID
    member_name: str
    pledges: List[StatementPledge]
    fines: List[StatementFine]
    payments: List[StatementPayment]
    totals: StatementTotals


# ---------- Annual report ----------

class AmountLine(BaseModel):
    label: str
    amount: Decimal


class YearReportResponse(BaseModel):
    year_id: uuid.UUID
    year: int
    status: str
    start_date: date
    end_date: date
    opening_balance: Decimal
    income_by_campaign: List[AmountLine]
    fine_income: Decimal
    welfare_fund_gifts: Decimal
    income_total: Decimal
    expenses_by_category: List[AmountLine]
    expenses_by_event: List[AmountLine]     # expenses paid from the welfare fund are labelled "Welfare fund"
    expenses_total: Decimal
    closing_balance: Decimal                # stored once closed, otherwise what it would be today
    is_final: bool                          # true once the year is closed