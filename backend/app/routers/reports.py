"""
Reports router. Read-only.
Officers (Chairman, Secretary, Treasurer) see campaign progress, any member's
statement and the annual report. Every member can see their own statement.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import get_current_member, require_role
from app.database import get_db
from app.models.member import Member
from app.schemas.reports import (
    AmountLine,
    CampaignReportResponse,
    MemberStatementResponse,
    OwingMember,
    StatementFine,
    StatementPayment,
    StatementPledge,
    StatementTotals,
    YearReportResponse,
)
from app.services import report_service

router = APIRouter()

VIEWERS = ("chairman", "secretary", "treasurer")


def _statement(data: dict) -> MemberStatementResponse:
    return MemberStatementResponse(
        member_id=data["member"].id,
        member_name=data["member"].name,
        pledges=[StatementPledge(**r) for r in data["pledges"]],
        fines=[StatementFine(**r) for r in data["fines"]],
        payments=[StatementPayment(**r) for r in data["payments"]],
        totals=StatementTotals(**data["totals"]),
    )


@router.get("/campaigns/{campaign_id}", response_model=CampaignReportResponse)
def campaign_progress(
    campaign_id: uuid.UUID,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    """Target, pledged, paid, outstanding, and who still owes."""
    d = report_service.campaign_report(db, family_id=actor.family_id, campaign_id=campaign_id)
    c = d["campaign"]
    return CampaignReportResponse(
        campaign_id=c.id, name=c.name, type=c.type, status=c.status, target_amount=c.target_amount,
        pledged_total=d["pledged_total"], paid_total=d["paid_total"],
        outstanding_total=d["outstanding_total"], pending_claims_total=d["pending_claims_total"],
        percent_of_target=d["percent_of_target"], pledge_count=d["pledge_count"],
        fully_paid_count=d["fully_paid_count"],
        still_owing=[OwingMember(**r) for r in d["still_owing"]],
    )


# "/me/statement" is declared before "/members/{id}/statement" only for readability;
# the paths differ, so order does not matter.
@router.get("/me/statement", response_model=MemberStatementResponse)
def my_statement(member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    return _statement(report_service.member_statement(db, family_id=member.family_id, member_id=member.id))


@router.get("/members/{member_id}/statement", response_model=MemberStatementResponse)
def member_statement(
    member_id: uuid.UUID,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    return _statement(report_service.member_statement(db, family_id=actor.family_id, member_id=member_id))


@router.get("/financial-years/{year_id}", response_model=YearReportResponse)
def annual_report(
    year_id: uuid.UUID,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    d = report_service.year_report(db, family_id=actor.family_id, year_id=year_id)
    y = d["year"]
    lines = lambda pairs: [AmountLine(label=label, amount=amount) for label, amount in pairs]  # noqa: E731
    return YearReportResponse(
        year_id=y.id, year=y.year, status=y.status, start_date=y.start_date, end_date=y.end_date,
        opening_balance=y.opening_balance,
        income_by_campaign=lines(d["income_by_campaign"]),
        fine_income=d["fine_income"], welfare_fund_gifts=d["welfare_fund_gifts"],
        income_total=d["income_total"],
        expenses_by_category=lines(d["expenses_by_category"]),
        expenses_by_event=lines(d["expenses_by_event"]),
        expenses_total=d["expenses_total"], closing_balance=d["closing_balance"],
        is_final=y.status == "closed",
    )