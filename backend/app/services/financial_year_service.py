"""
financial_year_service: creating and reading a family's financial years.
Framework-free: failures are domain exceptions. Services never commit.

Closing a year is NOT here yet. Closing needs the closing balance (opening +
confirmed income - approved expenses) and the "nothing pending" checks, which
depend on payments, fines and expenses. It is added in part 4 once those exist,
so a year can never be closed with a wrong balance.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.financial_year import FinancialYear
from app.models.member import Member
from app.services import audit_service


def get_year_in_family(db: Session, *, family_id: uuid.UUID, year_id: uuid.UUID) -> FinancialYear:
    """A year from the caller's own family, or NotFoundError."""
    year = (
        db.query(FinancialYear)
        .filter(FinancialYear.id == year_id, FinancialYear.family_id == family_id)
        .first()
    )
    if year is None:
        raise NotFoundError("Financial year not found")
    return year


def find_year_for_date(db: Session, *, family_id: uuid.UUID, on_date: date) -> Optional[FinancialYear]:
    """The year whose dates contain on_date, or None. Used by fines and expenses later."""
    return (
        db.query(FinancialYear)
        .filter(
            FinancialYear.family_id == family_id,
            FinancialYear.start_date <= on_date,
            FinancialYear.end_date >= on_date,
        )
        .first()
    )


def list_years(db: Session, *, family_id: uuid.UUID) -> List[FinancialYear]:
    return (
        db.query(FinancialYear)
        .filter(FinancialYear.family_id == family_id)
        .order_by(FinancialYear.start_date.desc())
        .all()
    )


def create_year(
    db: Session,
    *,
    actor: Member,
    year: int,
    start_date: date,
    end_date: date,
    opening_balance: Optional[Decimal],
) -> FinancialYear:
    family_id = actor.family_id

    # A family's years may not overlap.
    overlap = (
        db.query(FinancialYear)
        .filter(
            FinancialYear.family_id == family_id,
            FinancialYear.start_date <= end_date,
            FinancialYear.end_date >= start_date,
        )
        .first()
    )
    if overlap is not None:
        raise BusinessRuleError(
            f"These dates overlap the financial year {overlap.year} "
            f"({overlap.start_date} to {overlap.end_date})"
        )

    if db.query(FinancialYear.id).filter(
        FinancialYear.family_id == family_id, FinancialYear.year == year
    ).first():
        raise BusinessRuleError(f"A financial year labelled {year} already exists")

    # Later years carry the closing balance of the year before them.
    previous = (
        db.query(FinancialYear)
        .filter(FinancialYear.family_id == family_id, FinancialYear.end_date < start_date)
        .order_by(FinancialYear.end_date.desc())
        .first()
    )
    if previous is not None:
        if previous.status != "closed":
            raise BusinessRuleError(
                f"Close the financial year {previous.year} before creating a later one"
            )
        carried = previous.closing_balance if previous.closing_balance is not None else Decimal("0.00")
        if opening_balance is not None and opening_balance != carried:
            raise BusinessRuleError(
                "The opening balance is carried forward from the previous year. Leave it out"
            )
        opening = carried
    else:
        opening = opening_balance if opening_balance is not None else Decimal("0.00")

    financial_year = FinancialYear(
        family_id=family_id,
        year=year,
        start_date=start_date,
        end_date=end_date,
        status="open",
        opening_balance=opening,
    )
    db.add(financial_year)
    try:
        with db.begin_nested():  # savepoint: a race on the unique label fails cleanly
            db.flush()
    except IntegrityError:
        raise BusinessRuleError(f"A financial year labelled {year} already exists")

    audit_service.log_action(
        db,
        family_id=family_id,
        actor_member_id=actor.id,
        action="create",
        entity_type="financial_year",
        entity_id=financial_year.id,
        after_state={
            "year": year,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "opening_balance": str(opening),
        },
    )
    return financial_year