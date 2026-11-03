"""
Daily job: mark pledge installments overdue once their due date has passed.

Run from backend/:
    python -m scripts.mark_overdue_installments

Schedule it once a day with cron, for example at 00:30 (Nairobi time):
    30 0 * * * cd /path/to/backend && /path/to/venv/bin/python -m scripts.mark_overdue_installments >> /var/log/overdue.log 2>&1
"""
import app.models  # noqa: F401  (registers every model so relationships resolve)
from app.database import SessionLocal
from app.services import pledge_service


def main() -> None:
    db = SessionLocal()
    try:
        changed = pledge_service.mark_overdue_installments(db)
        db.commit()
        print(f"Overdue job done: {changed} installment(s) changed status.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()