"""
event_service: events (what money is FOR) and which campaigns fund them.
Framework-free: failures are domain exceptions. Services never commit.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.campaign import Campaign
from app.models.campaign_event import CampaignEvent
from app.models.event import Event
from app.models.expense import Expense
from app.models.member import Member
from app.models.pledge import Pledge
from app.services import audit_service
from app.services.campaign_service import get_campaign_in_family

# planned -> held -> closed. A planned event can also be closed without being held (called off).
ALLOWED_TRANSITIONS = {
    "planned": {"held", "closed"},
    "held": {"closed"},
    "closed": set(),
}


def get_event_in_family(
    db: Session, *, family_id: uuid.UUID, event_id: uuid.UUID, for_update: bool = False
) -> Event:
    query = db.query(Event).filter(Event.id == event_id, Event.family_id == family_id)
    if for_update:
        query = query.with_for_update()
    event = query.first()
    if event is None:
        raise NotFoundError("Event not found")
    return event


def create_event(
    db: Session,
    *,
    actor: Member,
    name: str,
    description: Optional[str],
    event_date: date,
    budget_amount: Optional[Decimal],
) -> Event:
    event = Event(
        family_id=actor.family_id,
        name=name,
        description=description,
        event_date=event_date,
        budget_amount=budget_amount,
        status="planned",
    )
    db.add(event)
    db.flush()
    audit_service.log_action(
        db,
        family_id=actor.family_id,
        actor_member_id=actor.id,
        action="create",
        entity_type="event",
        entity_id=event.id,
        after_state={
            "name": name,
            "event_date": event_date.isoformat(),
            "budget_amount": str(budget_amount) if budget_amount is not None else None,
        },
    )
    return event


def update_event(db: Session, *, actor: Member, event_id: uuid.UUID, changes: dict) -> Event:
    """changes: any of name, description, event_date, budget_amount, status."""
    event = get_event_in_family(db, family_id=actor.family_id, event_id=event_id, for_update=True)
    if event.status == "closed":
        raise BusinessRuleError("A closed event can't be changed")

    before, after = {}, {}
    new_status = changes.pop("status", None)
    if new_status is not None and new_status != event.status:
        if new_status not in ALLOWED_TRANSITIONS[event.status]:
            raise BusinessRuleError(f"An event can't go from {event.status} to {new_status}")
        before["status"], after["status"] = event.status, new_status
        event.status = new_status

    for field_name, value in changes.items():
        old = getattr(event, field_name)
        if value != old:
            before[field_name] = str(old) if old is not None else None
            after[field_name] = str(value) if value is not None else None
            setattr(event, field_name, value)

    if after:
        audit_service.log_action(
            db, family_id=actor.family_id, actor_member_id=actor.id,
            action="update", entity_type="event", entity_id=event.id,
            before_state=before, after_state=after,
        )
    return event


def link_campaigns(
    db: Session, *, actor: Member, event_id: uuid.UUID, links: List[dict]
) -> Event:
    """Replaces the event's campaign links. Each link: {campaign_id, allocated_amount (optional)}.
    All of one campaign's allocations, across every event, may not exceed its target."""
    event = get_event_in_family(db, family_id=actor.family_id, event_id=event_id, for_update=True)
    if event.status == "closed":
        raise BusinessRuleError("A closed event can't be changed")

    for link in links:
        campaign = get_campaign_in_family(
            db, family_id=actor.family_id, campaign_id=link["campaign_id"], for_update=True
        )
        if campaign.status == "cancelled":
            raise BusinessRuleError(f"The campaign '{campaign.name}' is cancelled")
        allocation = link.get("allocated_amount")
        if allocation is not None and campaign.target_amount is not None:
            others = (
                db.query(func.coalesce(func.sum(CampaignEvent.allocated_amount), 0))
                .filter(CampaignEvent.campaign_id == campaign.id, CampaignEvent.event_id != event.id)
                .scalar()
            )
            if Decimal(others) + allocation > campaign.target_amount:
                raise BusinessRuleError(
                    f"The allocations of '{campaign.name}' would add up to "
                    f"{Decimal(others) + allocation}, above its target of {campaign.target_amount}"
                )

    # Delete first and flush, so re-linking a campaign can't trip the unique constraint.
    db.query(CampaignEvent).filter(CampaignEvent.event_id == event.id).delete(synchronize_session=False)
    db.flush()
    for link in links:
        db.add(CampaignEvent(
            campaign_id=link["campaign_id"], event_id=event.id,
            allocated_amount=link.get("allocated_amount"),
        ))
    db.flush()
    audit_service.log_action(
        db, family_id=actor.family_id, actor_member_id=actor.id,
        action="update", entity_type="event", entity_id=event.id,
        after_state={"linked_campaigns": len(links)},
    )
    return event


# ---------- Reading ----------

def build_event_details(db: Session, events: List[Event]) -> List[dict]:
    """For each event: its linked campaigns, allocations, and approved spending."""
    if not events:
        return []
    ids = [e.id for e in events]

    link_rows = (
        db.query(CampaignEvent.event_id, Campaign.id, Campaign.name, CampaignEvent.allocated_amount)
        .join(Campaign, Campaign.id == CampaignEvent.campaign_id)
        .filter(CampaignEvent.event_id.in_(ids))
        .order_by(Campaign.name)
        .all()
    )
    campaign_ids = list({row[1] for row in link_rows})
    collected: Dict[uuid.UUID, Decimal] = {}
    if campaign_ids:
        for cid, total in (
            db.query(Pledge.campaign_id, func.coalesce(func.sum(Pledge.fulfilled_amount), 0))
            .filter(Pledge.campaign_id.in_(campaign_ids), Pledge.status != "cancelled")
            .group_by(Pledge.campaign_id)
            .all()
        ):
            collected[cid] = Decimal(total)

    spent = {
        event_id: Decimal(total)
        for event_id, total in (
            db.query(Expense.event_id, func.coalesce(func.sum(Expense.amount), 0))
            .filter(Expense.event_id.in_(ids), Expense.status == "approved")
            .group_by(Expense.event_id)
            .all()
        )
    }

    details = []
    for event in events:
        campaigns = [
            {
                "campaign_id": cid,
                "campaign_name": cname,
                "allocated_amount": allocated,
                "collected": collected.get(cid, Decimal("0.00")),
            }
            for ev_id, cid, cname, allocated in link_rows
            if ev_id == event.id
        ]
        allocations = [c["allocated_amount"] for c in campaigns if c["allocated_amount"] is not None]
        allocated_total = sum(allocations, Decimal("0.00"))
        spent_total = spent.get(event.id, Decimal("0.00"))
        details.append({
            "event": event,
            "campaigns": campaigns,
            "allocated_total": allocated_total,
            "spent_total": spent_total,
            "remaining_allocation": (allocated_total - spent_total) if allocations else None,
            "remaining_budget": (event.budget_amount - spent_total) if event.budget_amount is not None else None,
        })
    return details


def list_events(db: Session, *, family_id: uuid.UUID, status: Optional[str] = None) -> List[Event]:
    query = db.query(Event).filter(Event.family_id == family_id)
    if status is not None:
        query = query.filter(Event.status == status)
    return query.order_by(Event.event_date.desc(), Event.name).all()