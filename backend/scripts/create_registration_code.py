"""
Creates a one-time registration code for a new family and prints it ONCE.
Only the hash is saved, so the code can never be shown again.

Run from backend/:
    python -m scripts.create_registration_code "Kamau family"
    python -m scripts.create_registration_code "Kamau family" --days 7
"""
import argparse
from datetime import datetime, timedelta, timezone

import app.models  # noqa: F401  (registers every model so relationships resolve)
from app.core.security import generate_registration_code, hash_registration_code
from app.database import SessionLocal
from app.models.registration_code import RegistrationCode


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a family registration code")
    parser.add_argument("note", help="who the code is for, e.g. 'Kamau family'")
    parser.add_argument("--days", type=int, default=14, help="days until it expires (default 14)")
    args = parser.parse_args()

    code = generate_registration_code()
    db = SessionLocal()
    try:
        db.add(RegistrationCode(
            code_hash=hash_registration_code(code),
            note=args.note,
            expires_at=datetime.now(timezone.utc) + timedelta(days=args.days),
        ))
        db.commit()
    finally:
        db.close()

    print(f"Registration code for '{args.note}' (valid {args.days} days):")
    print(f"    {code}")
    print("Copy it now. It cannot be shown again.")


if __name__ == "__main__":
    main()