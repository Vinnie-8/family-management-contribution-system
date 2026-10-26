"""
Campaigns router. The Chairman creates, opens, closes and cancels campaigns and
sets their rules; the Chairman, Secretary and Treasurer can view them.
Thin by design: validate input, call one service function, commit, shape the response.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_role
from app.database import get_db
from app.models.member import Member
from app.schemas.campaigns import (
    AssessMemberRequest,
    CampaignCreateRequest,
    CampaignDetailResponse,
    CampaignResponse,
    OpenCampaignResponse,
    PledgeResponse,
    RuleResponse,
    SetRulesRequest,
)
from app.services import campaign_service

router = APIRouter()

CHAIRMAN = ("chairman",)
VIEWERS = ("chairman", "secretary", "treasurer")


def _detail(db: Session, campaign) -> CampaignDetailResponse:
    totals = campaign_service.campaign_totals(db, [campaign.id]).get(campaign.id)
    rules = [RuleResponse.model_validate(r) for r in campaign_service.get_rules(db, campaign.id)]
    return CampaignDetailResponse.from_campaign(campaign, totals, rules=rules)


@router.post("", response_model=CampaignDetailResponse, status_code=201)
def create_campaign(
    body: CampaignCreateRequest,
    actor: Member = Depends(require_role(*CHAIRMAN)),
    db: Session = Depends(get_db),
):
    campaign = campaign_service.create_campaign(
        db,
        actor=actor,
        financial_year_id=body.financial_year_id,
        name=body.name,
        type=body.type,
        start_date=body.start_date,
        end_date=body.end_date,
        target_amount=body.target_amount,
        includes_minors=body.includes_minors,
    )
    db.commit()
    return _detail(db, campaign)


@router.get("", response_model=List[CampaignResponse])
def list_campaigns(
    financial_year_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    campaigns = campaign_service.list_campaigns(
        db, family_id=actor.family_id, financial_year_id=financial_year_id, status=status
    )
    totals = campaign_service.campaign_totals(db, [c.id for c in campaigns])
    return [CampaignResponse.from_campaign(c, totals.get(c.id)) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
def read_campaign(
    campaign_id: uuid.UUID,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    campaign = campaign_service.get_campaign_in_family(
        db, family_id=actor.family_id, campaign_id=campaign_id
    )
    return _detail(db, campaign)


@router.put("/{campaign_id}/rules", response_model=CampaignDetailResponse)
def set_rules(
    campaign_id: uuid.UUID,
    body: SetRulesRequest,
    actor: Member = Depends(require_role(*CHAIRMAN)),
    db: Session = Depends(get_db),
):
    campaign_service.set_rules(
        db,
        actor=actor,
        campaign_id=campaign_id,
        rules=[r.model_dump() for r in body.rules],
    )
    db.commit()
    campaign = campaign_service.get_campaign_in_family(
        db, family_id=actor.family_id, campaign_id=campaign_id
    )
    return _detail(db, campaign)


@router.post("/{campaign_id}/open", response_model=OpenCampaignResponse)
def open_campaign(
    campaign_id: uuid.UUID,
    actor: Member = Depends(require_role(*CHAIRMAN)),
    db: Session = Depends(get_db),
):
    campaign, created = campaign_service.open_campaign(db, actor=actor, campaign_id=campaign_id)
    db.commit()
    totals = campaign_service.campaign_totals(db, [campaign.id]).get(campaign.id)
    return OpenCampaignResponse.from_campaign(campaign, totals, pledges_created=created)


@router.post("/{campaign_id}/close", response_model=CampaignResponse)
def close_campaign(
    campaign_id: uuid.UUID,
    actor: Member = Depends(require_role(*CHAIRMAN)),
    db: Session = Depends(get_db),
):
    campaign = campaign_service.close_campaign(db, actor=actor, campaign_id=campaign_id)
    db.commit()
    totals = campaign_service.campaign_totals(db, [campaign.id]).get(campaign.id)
    return CampaignResponse.from_campaign(campaign, totals)


@router.post("/{campaign_id}/cancel", response_model=CampaignResponse)
def cancel_campaign(
    campaign_id: uuid.UUID,
    actor: Member = Depends(require_role(*CHAIRMAN)),
    db: Session = Depends(get_db),
):
    campaign = campaign_service.cancel_campaign(db, actor=actor, campaign_id=campaign_id)
    db.commit()
    totals = campaign_service.campaign_totals(db, [campaign.id]).get(campaign.id)
    return CampaignResponse.from_campaign(campaign, totals)


@router.post("/{campaign_id}/pledges", response_model=PledgeResponse, status_code=201)
def assess_member(
    campaign_id: uuid.UUID,
    body: AssessMemberRequest,
    actor: Member = Depends(require_role(*CHAIRMAN)),
    db: Session = Depends(get_db),
):
    """Assess a member who joined after the fixed campaign opened."""
    pledge = campaign_service.assess_member(
        db, actor=actor, campaign_id=campaign_id, member_id=body.member_id
    )
    db.commit()
    name = campaign_service.get_member_name(db, pledge.member_id)
    return PledgeResponse.from_pledge(pledge, name)


@router.get("/{campaign_id}/pledges", response_model=List[PledgeResponse])
def list_campaign_pledges(
    campaign_id: uuid.UUID,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    """Who owes, how much, and how much they have paid."""
    rows = campaign_service.list_campaign_pledges(
        db, family_id=actor.family_id, campaign_id=campaign_id
    )
    return [PledgeResponse.from_pledge(p, name) for p, name in rows]