"""
campaign_service: creating campaigns, setting their rules, opening them
(which assesses every eligible member of a fixed campaign), closing and cancelling.
Framework-free: failures are domain exceptions. Services never commit.

Lifecycle: draft -> open -> closed, or cancelled from draft/open.
Rules can only change while a campaign is a draft; once it opens, amounts are
a snapshot in the pledges.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.campaign import Campaign
from app.models.contribution_rule import ContributionRule
from app.models.guardian_link import GuardianLink
from app.models.member import Member
from app.models.payment import Payment
from app.models.pledge import Pledge
from app.services import audit_service
from app.services.financial_year_service import get_year_in_family
from app.services.member_service import get_member_in_family

DEFAULT_CATEGORY = "default"


# ---------- Reading ----------

def get_campaign_in_family(
    db: Session, *, family_id: uuid.UUID, campaign_id: uuid.UUID, for_update: bool = False
) -> Campaign:
    """A campaign from the caller's own family, or NotFoundError.
    for_update locks the row, so two officers can't open or cancel it at once."""
    query = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.family_id == family_id)
    if for_update:
        query = query.with_for_update()
    campaign = query.first()
    if campaign is None:
        raise NotFoundError("Campaign not found")
    return campaign


def get_member_name(db: Session, member_id: uuid.UUID) -> str:
    return db.query(Member.name).filter(Member.id == member_id).scalar()


def get_rules(db: Session, campaign_id: uuid.UUID) -> List[ContributionRule]:
    return (
        db.query(ContributionRule)
        .filter(ContributionRule.campaign_id == campaign_id)
        .order_by(ContributionRule.member_category)
        .all()
    )


def campaign_totals(
    db: Session, campaign_ids: List[uuid.UUID]
) -> Dict[uuid.UUID, Tuple[int, Decimal, Decimal]]:
    """{campaign_id: (pledge_count, pledged_total, fulfilled_total)}, cancelled pledges excluded."""
    if not campaign_ids:
        return {}
    rows = (
        db.query(
            Pledge.campaign_id,
            func.count(Pledge.id),
            func.coalesce(func.sum(Pledge.amount), 0),
            func.coalesce(func.sum(Pledge.fulfilled_amount), 0),
        )
        .filter(Pledge.campaign_id.in_(campaign_ids), Pledge.status != "cancelled")
        .group_by(Pledge.campaign_id)
        .all()
    )
    return {cid: (count, Decimal(pledged), Decimal(fulfilled)) for cid, count, pledged, fulfilled in rows}


def list_campaigns(
    db: Session,
    *,
    family_id: uuid.UUID,
    financial_year_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
) -> List[Campaign]:
    query = db.query(Campaign).filter(Campaign.family_id == family_id)
    if financial_year_id is not None:
        query = query.filter(Campaign.financial_year_id == financial_year_id)
    if status is not None:
        query = query.filter(Campaign.status == status)
    return query.order_by(Campaign.start_date.desc(), Campaign.name).all()


def list_campaign_pledges(
    db: Session, *, family_id: uuid.UUID, campaign_id: uuid.UUID
) -> List[Tuple[Pledge, str]]:
    """Every pledge of a campaign with the member's name: who owes, who has paid."""
    get_campaign_in_family(db, family_id=family_id, campaign_id=campaign_id)
    return (
        db.query(Pledge, Member.name)
        .join(Member, Member.id == Pledge.member_id)
        .filter(Pledge.campaign_id == campaign_id, Pledge.family_id == family_id)
        .order_by(Member.name)
        .all()
    )


# ---------- Creating and setting rules ----------

def create_campaign(
    db: Session,
    *,
    actor: Member,
    financial_year_id: uuid.UUID,
    name: str,
    type: str,
    start_date: date,
    end_date: date,
    target_amount: Optional[Decimal],
    includes_minors: bool,
) -> Campaign:
    year = get_year_in_family(db, family_id=actor.family_id, year_id=financial_year_id)
    if year.status != "open":
        raise BusinessRuleError("That financial year is closed")
    if start_date < year.start_date or end_date > year.end_date:
        raise BusinessRuleError(
            f"Campaign dates must fall inside the financial year ({year.start_date} to {year.end_date})"
        )

    campaign = Campaign(
        family_id=actor.family_id,
        financial_year_id=year.id,
        created_by=actor.id,
        name=name,
        type=type,
        start_date=start_date,
        end_date=end_date,
        target_amount=target_amount,
        includes_minors=includes_minors,
        status="draft",
    )
    db.add(campaign)
    db.flush()
    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="create",
        entity_type="campaign",
        entity_id=campaign.id,
        after_state={"name": name, "type": type, "status": "draft"},
    )
    return campaign


def set_rules(
    db: Session, *, actor: Member, campaign_id: uuid.UUID, rules: List[dict]
) -> List[ContributionRule]:
    """Replaces the whole rule set of a draft fixed campaign.
    Each rule: {member_category, cash_amount, in_kind_item}."""
    campaign = get_campaign_in_family(
        db, family_id=actor.family_id, campaign_id=campaign_id, for_update=True
    )
    if campaign.type != "fixed":
        raise BusinessRuleError("Only fixed campaigns have contribution rules")
    if campaign.status != "draft":
        raise BusinessRuleError("Rules can only be changed while the campaign is a draft")

    # Delete first and flush, so re-adding the same category can't trip the unique constraint.
    db.query(ContributionRule).filter(ContributionRule.campaign_id == campaign.id).delete(
        synchronize_session=False
    )
    db.flush()
    for rule in rules:
        db.add(ContributionRule(
            campaign_id=campaign.id,
            member_category=rule["member_category"],
            cash_amount=rule["cash_amount"],
            in_kind_item=rule.get("in_kind_item"),
        ))
    db.flush()
    db.expire(campaign, ["contribution_rules"])

    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="update",
        entity_type="contribution_rule",
        entity_id=campaign.id,  # the rules are identified by their campaign
        after_state={"campaign_id": str(campaign.id), "rule_count": len(rules)},
    )
    return get_rules(db, campaign.id)


# ---------- Assessing members ----------

def _rule_lookup(rules: List[ContributionRule]) -> Dict[str, ContributionRule]:
    return {r.member_category.strip().casefold(): r for r in rules}


def _find_rule(lookup: Dict[str, ContributionRule], member: Member) -> Optional[ContributionRule]:
    """The rule for the member's category, or the default rule, or None."""
    key = (member.category or "").strip().casefold()
    return lookup.get(key) or lookup.get(DEFAULT_CATEGORY)


def _pledged_by(db: Session, member: Member, fallback_member_id: uuid.UUID) -> uuid.UUID:
    """Who makes the commitment: the member, or the guardian for a minor."""
    if member.is_minor:
        link = db.query(GuardianLink).filter(GuardianLink.minor_member_id == member.id).first()
        return link.guardian_member_id if link else fallback_member_id
    return member.id


def _eligible_members(db: Session, campaign: Campaign) -> List[Member]:
    """Active adults, plus active minors when the campaign includes them."""
    members = (
        db.query(Member)
        .options(joinedload(Member.family))  # is_minor needs the family's age limit
        .filter(Member.family_id == campaign.family_id, Member.is_active.is_(True))
        .order_by(Member.name)
        .all()
    )
    return [m for m in members if campaign.includes_minors or not m.is_minor]


def open_campaign(db: Session, *, actor: Member, campaign_id: uuid.UUID) -> Tuple[Campaign, int]:
    """Opens a draft campaign. For a fixed campaign this assesses every eligible
    member in one go: all pledges are created, or none are. Returns (campaign, pledges_created)."""
    campaign = get_campaign_in_family(
        db, family_id=actor.family_id, campaign_id=campaign_id, for_update=True
    )
    if campaign.status != "draft":
        raise BusinessRuleError(f"Only a draft campaign can be opened. This one is {campaign.status}")

    year = get_year_in_family(db, family_id=actor.family_id, year_id=campaign.financial_year_id)
    if year.status != "open":
        raise BusinessRuleError("That financial year is closed")
    if campaign.end_date < date.today():
        raise BusinessRuleError("This campaign's end date has already passed")

    created = 0
    if campaign.type == "fixed":
        rules = get_rules(db, campaign.id)
        if not rules:
            raise BusinessRuleError("Add contribution rules before opening a fixed campaign")
        lookup = _rule_lookup(rules)

        members = _eligible_members(db, campaign)
        if not members:
            raise BusinessRuleError("There are no eligible members to assess")

        plan, missing = [], []
        for member in members:
            rule = _find_rule(lookup, member)
            if rule is None:
                missing.append(member.name)
            else:
                plan.append((member, rule))
        if missing:
            shown = ", ".join(missing[:10]) + (f" and {len(missing) - 10} more" if len(missing) > 10 else "")
            raise BusinessRuleError(
                f"No contribution rule for the category of: {shown}. "
                f"Add a rule for their category or a '{DEFAULT_CATEGORY}' rule"
            )

        for member, rule in plan:
            db.add(Pledge(
                family_id=campaign.family_id,
                member_id=member.id,
                campaign_id=campaign.id,
                pledged_by=_pledged_by(db, member, actor.id),
                source="assessed",
                amount=rule.cash_amount,
                fulfilled_amount=0,
                status="active",
            ))
        db.flush()
        created = len(plan)

    campaign.status = "open"
    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="open_campaign",
        entity_type="campaign",
        entity_id=campaign.id,
        before_state={"status": "draft"},
        after_state={"status": "open", "pledges_created": created},
    )
    return campaign, created


def assess_member(
    db: Session, *, actor: Member, campaign_id: uuid.UUID, member_id: uuid.UUID
) -> Pledge:
    """Assesses one member of an already-open fixed campaign (a member who joined
    after it opened). The amount comes from the campaign's rules."""
    campaign = get_campaign_in_family(
        db, family_id=actor.family_id, campaign_id=campaign_id, for_update=True
    )
    if campaign.type != "fixed" or campaign.status != "open":
        raise BusinessRuleError("Members can only be assessed on an open fixed campaign")

    member = get_member_in_family(db, family_id=actor.family_id, member_id=member_id)
    if not member.is_active:
        raise BusinessRuleError("This member is deactivated")
    if member.is_minor and not campaign.includes_minors:
        raise BusinessRuleError("This campaign does not include minors")

    if db.query(Pledge.id).filter(
        Pledge.member_id == member.id, Pledge.campaign_id == campaign.id
    ).first():
        raise BusinessRuleError("This member already has a pledge on this campaign")

    rule = _find_rule(_rule_lookup(get_rules(db, campaign.id)), member)
    if rule is None:
        raise BusinessRuleError(
            f"No contribution rule for this member's category. Add a '{DEFAULT_CATEGORY}' rule"
        )

    pledge = Pledge(
        family_id=campaign.family_id,
        member_id=member.id,
        campaign_id=campaign.id,
        pledged_by=_pledged_by(db, member, actor.id),
        source="assessed",
        amount=rule.cash_amount,
        fulfilled_amount=0,
        status="active",
    )
    db.add(pledge)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        raise BusinessRuleError("This member already has a pledge on this campaign")

    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="create",
        entity_type="pledge",
        entity_id=pledge.id,
        after_state={
            "campaign_id": str(campaign.id),
            "member_id": str(member.id),
            "amount": str(pledge.amount),
            "source": "assessed",
        },
    )
    return pledge


# ---------- Closing and cancelling ----------

def close_campaign(db: Session, *, actor: Member, campaign_id: uuid.UUID) -> Campaign:
    """Stops new pledges and payments. Existing records stay."""
    campaign = get_campaign_in_family(
        db, family_id=actor.family_id, campaign_id=campaign_id, for_update=True
    )
    if campaign.status != "open":
        raise BusinessRuleError(f"Only an open campaign can be closed. This one is {campaign.status}")
    campaign.status = "closed"
    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="close_campaign",
        entity_type="campaign",
        entity_id=campaign.id,
        before_state={"status": "open"},
        after_state={"status": "closed"},
    )
    return campaign


def cancel_campaign(db: Session, *, actor: Member, campaign_id: uuid.UUID) -> Campaign:
    """Withdraws a campaign opened by mistake. Not allowed once any payment exists
    (pending or confirmed): close it instead, and void the payments with reasons."""
    campaign = get_campaign_in_family(
        db, family_id=actor.family_id, campaign_id=campaign_id, for_update=True
    )
    if campaign.status not in ("draft", "open"):
        raise BusinessRuleError(f"Only a draft or open campaign can be cancelled. This one is {campaign.status}")

    has_payments = (
        db.query(Payment.id)
        .join(Pledge, Pledge.id == Payment.pledge_id)
        .filter(Pledge.campaign_id == campaign.id, Payment.status.in_(("pending", "confirmed")))
        .first()
    )
    if has_payments is not None:
        raise BusinessRuleError(
            "This campaign has payments. Close it instead, or void the payments first"
        )

    before = campaign.status
    db.query(Pledge).filter(
        Pledge.campaign_id == campaign.id, Pledge.status == "active"
    ).update({"status": "cancelled"}, synchronize_session=False)
    campaign.status = "cancelled"
    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="cancel_campaign",
        entity_type="campaign",
        entity_id=campaign.id,
        before_state={"status": before},
        after_state={"status": "cancelled"},
    )
    return campaign