"""
pledge_service: voluntary pledges, installment plans, cancelling, and the
installment status job.
Framework-free: failures are domain exceptions. Services never commit.

Assessed pledges (fixed campaigns) are created by campaign_service. Everything
about a pledge's paid amount belongs to payment_service; this module only
recomputes the pledge's status and installments when that amount changes.
"""
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import today_local
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.campaign import Campaign
from app.models.guardian_link import GuardianLink
from app.models.member import Member
from app.models.payment import Payment
from app.models.pledge import Pledge
from app.models.pledge_installment import PledgeInstallment
from app.services import audit_service
from app.services.campaign_service import get_campaign_in_family
from app.services.member_service import get_member_in_family


@dataclass
class PledgeView:
    pledge: Pledge
    member_name: str
    campaign_name: str
    campaign_type: str
    installments: List[PledgeInstallment] = field(default_factory=list)


# ---------- Reading ----------

def get_pledge_in_family(
    db: Session, *, family_id: uuid.UUID, pledge_id: uuid.UUID, for_update: bool = False
) -> Pledge:
    """A pledge from the caller's own family, or NotFoundError."""
    query = db.query(Pledge).filter(Pledge.id == pledge_id, Pledge.family_id == family_id)
    if for_update:
        query = query.with_for_update()
    pledge = query.first()
    if pledge is None:
        raise NotFoundError("Pledge not found")
    return pledge


def _views(db: Session, rows) -> List[PledgeView]:
    """rows: [(Pledge, member_name, campaign_name, campaign_type)] -> views with installments (one query)."""
    ids = [r[0].id for r in rows]
    by_pledge: Dict[uuid.UUID, List[PledgeInstallment]] = {}
    if ids:
        installments = (
            db.query(PledgeInstallment)
            .filter(PledgeInstallment.pledge_id.in_(ids))
            .order_by(PledgeInstallment.due_date)
            .all()
        )
        for i in installments:
            by_pledge.setdefault(i.pledge_id, []).append(i)
    return [
        PledgeView(p, member_name, campaign_name, campaign_type, by_pledge.get(p.id, []))
        for p, member_name, campaign_name, campaign_type in rows
    ]


def list_pledges(
    db: Session,
    *,
    family_id: uuid.UUID,
    campaign_id: Optional[uuid.UUID] = None,
    member_id: Optional[uuid.UUID] = None,
    involving: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
) -> List[PledgeView]:
    """involving: pledges of this member, or that this member made (a guardian for a minor)."""
    query = (
        db.query(Pledge, Member.name, Campaign.name, Campaign.type)
        .join(Member, Member.id == Pledge.member_id)
        .join(Campaign, Campaign.id == Pledge.campaign_id)
        .filter(Pledge.family_id == family_id)
    )
    if campaign_id is not None:
        query = query.filter(Pledge.campaign_id == campaign_id)
    if member_id is not None:
        query = query.filter(Pledge.member_id == member_id)
    if involving is not None:
        query = query.filter((Pledge.member_id == involving) | (Pledge.pledged_by == involving))
    if status is not None:
        query = query.filter(Pledge.status == status)
    return _views(db, query.order_by(Campaign.name, Member.name).all())


def get_pledge_view(db: Session, *, family_id: uuid.UUID, pledge_id: uuid.UUID) -> PledgeView:
    pledge = get_pledge_in_family(db, family_id=family_id, pledge_id=pledge_id)
    row = (
        db.query(Pledge, Member.name, Campaign.name, Campaign.type)
        .join(Member, Member.id == Pledge.member_id)
        .join(Campaign, Campaign.id == Pledge.campaign_id)
        .filter(Pledge.id == pledge.id)
        .one()
    )
    return _views(db, [row])[0]


# ---------- Installment statuses ----------

def refresh_installment_statuses(
    db: Session, pledge: Pledge, today: Optional[date] = None
) -> int:
    """Recomputes each installment's status from what has been paid. Payments apply
    oldest-first: an installment is paid when the pledge's paid amount covers it and
    every earlier one. Returns how many statuses changed."""
    today = today or today_local()
    installments = (
        db.query(PledgeInstallment)
        .filter(PledgeInstallment.pledge_id == pledge.id)
        .order_by(PledgeInstallment.due_date)
        .all()
    )
    cumulative = Decimal("0")
    changed = 0
    for inst in installments:
        cumulative += inst.amount
        if pledge.fulfilled_amount >= cumulative:
            new_status = "paid"
        elif inst.due_date < today:
            new_status = "overdue"
        else:
            new_status = "pending"
        if inst.status != new_status:
            inst.status = new_status
            changed += 1
    return changed


def recompute_pledge_status(db: Session, pledge: Pledge) -> None:
    """Called by payment_service after the paid amount changes."""
    if pledge.status != "cancelled":
        pledge.status = "fulfilled" if pledge.fulfilled_amount >= pledge.amount else "active"
    refresh_installment_statuses(db, pledge)


def mark_overdue_installments(db: Session) -> int:
    """Daily job: refreshes installments of every pledge that still has an unpaid one.
    Returns how many installments changed status. The caller commits."""
    today = today_local()
    pledges = (
        db.query(Pledge)
        .join(PledgeInstallment, PledgeInstallment.pledge_id == Pledge.id)
        .filter(Pledge.status == "active", PledgeInstallment.status != "paid")
        .distinct()
        .all()
    )
    return sum(refresh_installment_statuses(db, p, today) for p in pledges)


# ---------- Voluntary pledges ----------

def _default_pledger(db: Session, member: Member, fallback_member_id: uuid.UUID) -> uuid.UUID:
    """Who made the commitment: the member, or their guardian if they are a minor."""
    if member.is_minor:
        link = db.query(GuardianLink).filter(GuardianLink.minor_member_id == member.id).first()
        return link.guardian_member_id if link else fallback_member_id
    return member.id


def make_voluntary_pledge(
    db: Session,
    *,
    actor: Member,
    campaign_id: uuid.UUID,
    member_id: uuid.UUID,
    amount: Decimal,
    pledged_by_id: Optional[uuid.UUID] = None,
) -> Pledge:
    """Creates a voluntary pledge, or changes the member's existing one on a
    pledge or emergency campaign. The amount can go up, or down as far as what is already paid."""
    campaign = get_campaign_in_family(
        db, family_id=actor.family_id, campaign_id=campaign_id, for_update=True
    )
    if campaign.type == "fixed":
        raise BusinessRuleError(
            "A fixed campaign assesses every member automatically. Members don't pledge to it"
        )
    if campaign.status != "open":
        raise BusinessRuleError(f"This campaign is {campaign.status}. Pledges are accepted only while it is open")

    member = get_member_in_family(db, family_id=actor.family_id, member_id=member_id)
    if not member.is_active:
        raise BusinessRuleError("This member is deactivated")

    existing = (
        db.query(Pledge)
        .filter(Pledge.member_id == member.id, Pledge.campaign_id == campaign.id)
        .with_for_update()
        .first()
    )

    if existing is not None:
        if existing.status == "cancelled":
            # Nothing was ever paid on a cancelled pledge, so it can simply be revived.
            before = {"status": "cancelled", "amount": str(existing.amount)}
            existing.status = "active"
            existing.amount = amount
            existing.pledged_by = pledged_by_id or _default_pledger(db, member, actor.id)
        else:
            if amount < existing.fulfilled_amount:
                raise BusinessRuleError(
                    f"{existing.fulfilled_amount} is already paid. The pledge can't go below that"
                )
            has_plan = db.query(PledgeInstallment.id).filter(PledgeInstallment.pledge_id == existing.id).first()
            if has_plan is not None and amount != existing.amount:
                raise BusinessRuleError("Clear the installment plan before changing the amount")
            before = {"amount": str(existing.amount), "status": existing.status}
            existing.amount = amount
        recompute_pledge_status(db, existing)
        db.flush()
        audit_service.log_action(
            db,
            family_id=actor.family_id,
            actor_member_id=actor.id,
            action="update",
            entity_type="pledge",
            entity_id=existing.id,
            before_state=before,
            after_state={"amount": str(amount), "status": existing.status},
        )
        return existing

    pledger = pledged_by_id or _default_pledger(db, member, actor.id)
    if pledged_by_id is not None:
        get_member_in_family(db, family_id=actor.family_id, member_id=pledged_by_id)

    pledge = Pledge(
        family_id=actor.family_id,
        member_id=member.id,
        campaign_id=campaign.id,
        pledged_by=pledger,
        source="voluntary",
        amount=amount,
        fulfilled_amount=Decimal("0.00"),
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
            "amount": str(amount),
            "source": "voluntary",
        },
    )
    return pledge


# ---------- Installments ----------

def set_installments(
    db: Session, *, actor: Member, pledge_id: uuid.UUID, items: List[dict]
) -> Pledge:
    """Replaces the installment plan. Each item: {amount, due_date}. They must add up
    exactly to the pledge amount. An empty list clears the plan."""
    pledge = get_pledge_in_family(db, family_id=actor.family_id, pledge_id=pledge_id, for_update=True)
    if pledge.status != "active":
        raise BusinessRuleError(f"This pledge is {pledge.status}. Only an active pledge can have a plan")

    if items:
        total = sum((i["amount"] for i in items), Decimal("0"))
        if total != pledge.amount:
            raise BusinessRuleError(
                f"The installments add up to {total}, but the pledge is {pledge.amount}. They must match exactly"
            )

    # Delete first and flush, so a re-entered due date can't trip the unique constraint.
    db.query(PledgeInstallment).filter(PledgeInstallment.pledge_id == pledge.id).delete(
        synchronize_session=False
    )
    db.flush()
    for item in items:
        db.add(PledgeInstallment(
            pledge_id=pledge.id, amount=item["amount"], due_date=item["due_date"], status="pending"
        ))
    db.flush()
    refresh_installment_statuses(db, pledge)

    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="update",
        entity_type="pledge",
        entity_id=pledge.id,
        after_state={"installments": len(items)},
    )
    return pledge


# ---------- Cancelling ----------

def cancel_pledge(db: Session, *, actor: Member, pledge_id: uuid.UUID, reason: str) -> Pledge:
    """Withdraws a pledge. Only possible while nothing has been paid or claimed on it."""
    pledge = get_pledge_in_family(db, family_id=actor.family_id, pledge_id=pledge_id, for_update=True)
    if pledge.status != "active":
        raise BusinessRuleError(f"Only an active pledge can be cancelled. This one is {pledge.status}")
    if pledge.fulfilled_amount > 0:
        raise BusinessRuleError("Money has been paid on this pledge. Void those payments first")
    pending = (
        db.query(Payment.id)
        .filter(Payment.pledge_id == pledge.id, Payment.status == "pending")
        .first()
    )
    if pending is not None:
        raise BusinessRuleError("A payment claim is waiting on this pledge. Reject it first")

    pledge.status = "cancelled"
    db.query(PledgeInstallment).filter(PledgeInstallment.pledge_id == pledge.id).delete(
        synchronize_session=False
    )
    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="update",
        entity_type="pledge",
        entity_id=pledge.id,
        before_state={"status": "active"},
        after_state={"status": "cancelled", "reason": reason},
    )
    return pledge