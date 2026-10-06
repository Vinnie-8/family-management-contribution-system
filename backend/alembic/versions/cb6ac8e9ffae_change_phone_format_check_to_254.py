"""change phone format check to +254

Revision ID: cb6ac8e9ffae
Revises: 4ef254077e8d
Create Date: 2026-10-06 17:02:34.042208

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb6ac8e9ffae'
down_revision: Union[str, Sequence[str], None] = '4ef254077e8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("check_phone_format", "members", type_="check")
    op.create_check_constraint(
        "check_phone_format",
        "members",
        r"phone_number IS NULL OR phone_number ~ '^\+254[17][0-9]{8}$'",
    )


def downgrade() -> None:
    op.drop_constraint("check_phone_format", "members", type_="check")
    op.create_check_constraint(
        "check_phone_format",
        "members",
        "phone_number IS NULL OR phone_number ~ '^[0-9]{10}$'",
    )
