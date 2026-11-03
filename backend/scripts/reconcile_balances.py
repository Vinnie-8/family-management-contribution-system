"""
Check that every stored total matches the payments and expenses behind it.
Changes nothing. Exits with status 1 if anything differs, so cron or a monitor can alert.

Run from backend/:
    python -m scripts.reconcile_balances

Schedule it, for example every night at 02:00:
    0 2 * * * cd /path/to/backend && /path/to/venv/bin/python -m scripts.reconcile_balances >> /var/log/reconcile.log 2>&1
"""
import sys

import app.models  # noqa: F401  (registers every model so relationships resolve)
from app.database import SessionLocal
from app.services import reconcile_service


def main() -> int:
    db = SessionLocal()
    try:
        differences = reconcile_service.find_differences(db)
    finally:
        db.close()
    if not differences:
        print("Reconcile done: every stored total matches its records.")
        return 0
    print(f"Reconcile found {len(differences)} difference(s):")
    for d in differences:
        print(f"  {d['kind']} {d['id']} (family {d['family_id']}): stored {d['stored']}, expected {d['expected']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())