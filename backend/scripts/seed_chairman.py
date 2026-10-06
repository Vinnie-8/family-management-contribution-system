"""One-time script: creates a family, the 'chairman' role, and the first chairman."""
from app.core.security import hash_password
from app.database import SessionLocal  # adjust: whatever get_db uses
from app.models.family import Family  # adjust
from app.models.member import Member
from app.models.member_role import MemberRole
from app.models.role import Role

db = SessionLocal()
try:
    family = Family(name="Kamendes Family")  # adjust fields
    db.add(family)
    db.flush()

    role = db.query(Role).filter(Role.name == "chairman").first()
    if role is None:
        role = Role(name="chairman",
                    description="Head of the family; can onboard members and manage the system",) 
        db.add(role)
        db.flush()

    chairman = Member(
        family_id=family.id,
        name="Chairman Test",
        phone_number="+254712345678",
        is_minor=False,
        is_active=True,
        hashed_password=hash_password("ChangeMe123"),
        must_change_password=False,  # so the chairman can use every route right away
    )
    db.add(chairman)
    db.flush()

    db.add(MemberRole(member_id=chairman.id, role_id=role.id))
    db.commit()
    print("Chairman created. Log in with +254712345678 / ChangeMe123")
finally:
    db.close()