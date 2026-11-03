"""
Events router. The Chairman and Secretary create events and link campaigns to them;
the Treasurer can view them.
Thin by design: validate input, call one service function, commit, shape the response.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_role
from app.database import get_db
from app.models.member import Member
from app.schemas.events import (
    EventCreateRequest,
    EventResponse,
    EventUpdateRequest,
    LinkCampaignsRequest,
)
from app.services import event_service

router = APIRouter()

PLANNERS = ("chairman", "secretary")
VIEWERS = ("chairman", "secretary", "treasurer")


def _response(db: Session, event) -> EventResponse:
    return EventResponse.from_detail(event_service.build_event_details(db, [event])[0])


@router.post("", response_model=EventResponse, status_code=201)
def create_event(
    body: EventCreateRequest,
    actor: Member = Depends(require_role(*PLANNERS)),
    db: Session = Depends(get_db),
):
    event = event_service.create_event(
        db,
        actor=actor,
        name=body.name,
        description=body.description,
        event_date=body.event_date,
        budget_amount=body.budget_amount,
    )
    db.commit()
    return _response(db, event)


@router.get("", response_model=List[EventResponse])
def list_events(
    status: Optional[str] = None,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    events = event_service.list_events(db, family_id=actor.family_id, status=status)
    return [EventResponse.from_detail(d) for d in event_service.build_event_details(db, events)]


@router.get("/{event_id}", response_model=EventResponse)
def read_event(
    event_id: uuid.UUID,
    actor: Member = Depends(require_role(*VIEWERS)),
    db: Session = Depends(get_db),
):
    event = event_service.get_event_in_family(db, family_id=actor.family_id, event_id=event_id)
    return _response(db, event)


@router.patch("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: uuid.UUID,
    body: EventUpdateRequest,
    actor: Member = Depends(require_role(*PLANNERS)),
    db: Session = Depends(get_db),
):
    changes = {name: getattr(body, name) for name in body.model_fields_set if getattr(body, name) is not None}
    event = event_service.update_event(db, actor=actor, event_id=event_id, changes=changes)
    db.commit()
    return _response(db, event)


@router.put("/{event_id}/campaigns", response_model=EventResponse)
def link_campaigns(
    event_id: uuid.UUID,
    body: LinkCampaignsRequest,
    actor: Member = Depends(require_role(*PLANNERS)),
    db: Session = Depends(get_db),
):
    event = event_service.link_campaigns(
        db, actor=actor, event_id=event_id, links=[l.model_dump() for l in body.links]
    )
    db.commit()
    return _response(db, event)