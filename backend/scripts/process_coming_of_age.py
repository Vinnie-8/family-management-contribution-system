"""
Daily job: invite minors who have reached their family's age limit.

Run from backend/:
    python -m scripts.process_coming_of_age

Schedule it once a day with cron, for example at 06:00:
    0 6 * * * cd /path/to/backend && /path/to/venv/bin/python -m scripts.process_coming_of_age >> /var/log/coming_of_age.log 2>&1
"""
import app.models  # noqa: F401  (registers every model so relationships resolve)
from app.database import SessionLocal
from app.services import member_service


def main() -> None:
    db = SessionLocal()
    try:
        result = member_service.invite_members_coming_of_age(db)
        db.commit()
        print(
            f"Coming-of-age job done: {result['invited']} invited, "
            f"{result['officers_notified']} officer notifications, "
            f"{result['already_invited']} already had a live invite."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()