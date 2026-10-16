"""households, dob, activation and registration

Revision ID: 083676136bab
Revises: cb6ac8e9ffae
Create Date: 2026-10-13 16:50:31.764477

Hand-edited after autogenerate. Autogenerate does not see CHECK constraint
changes, data backfills or seed data, and it would have made
members.household_id NOT NULL before any household existed (which fails
when members already exist).
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '083676136bab'
down_revision: Union[str, Sequence[str], None] = 'cb6ac8e9ffae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Frozen copies: a migration must not import from app code, because the
# models change over time but a migration must always do the same thing.
OLD_AUDIT_ACTIONS = ("create", "update", "delete", "deactivate_member", "reset_password")
OLD_ENTITY_TYPES = ("member", "household", "contribution_rule")
NEW_AUDIT_ACTIONS = OLD_AUDIT_ACTIONS + (
    "register_family", "send_invite", "activate_member", "login",
    "change_password", "view_date_of_birth", "change_household",
)
NEW_ENTITY_TYPES = OLD_ENTITY_TYPES + ("family",)

ROLES = (
    ("member", "Every person in a family. Can view their own records."),
    ("chairman", "Heads the family. Registers it, onboards members, manages households and roles."),
    ("secretary", "Helps run the family. Onboards members and manages households and minutes."),
    ("treasurer", "Manages money. Records payments, pledges, fines and expenses."),
    ("guardian", "Acts for a minor. Receives notifications on the minor's behalf."),
)


def _in_list(column: str, values: tuple) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # --- New tables ---
    op.create_table('registration_codes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('note', sa.String(length=100), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('used_by_family_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['used_by_family_id'], ['families.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_hash'),
    )
    op.create_table('activation_tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('member_id', sa.UUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('sent_to', sa.String(length=50), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index(op.f('ix_activation_tokens_member_id'), 'activation_tokens', ['member_id'], unique=False)

    # --- families: per-family minor age limit ---
    op.add_column('families', sa.Column('age_of_majority', sa.Integer(), server_default='18', nullable=False))
    op.create_check_constraint('check_age_of_majority_range', 'families', 'age_of_majority BETWEEN 1 AND 30')

    # --- households: head and lineage ---
    op.add_column('households', sa.Column('head_member_id', sa.UUID(), nullable=True))
    op.add_column('households', sa.Column('parent_household_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_households_parent_household_id'), 'households', ['parent_household_id'], unique=False)
    op.create_foreign_key('fk_households_head_member', 'households', 'members', ['head_member_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_households_parent_household', 'households', 'households', ['parent_household_id'], ['id'], ondelete='SET NULL')
    op.create_check_constraint('check_household_not_own_parent', 'households', 'parent_household_id IS NULL OR parent_household_id <> id')

    # --- members: new columns ---
    op.add_column('members', sa.Column('date_of_birth', sa.Date(), nullable=True))
    op.add_column('members', sa.Column('invite_contact', sa.String(length=50), nullable=True))

    # --- Backfill: every existing member needs a household before household_id can be required ---
    family_ids = bind.execute(
        sa.text("SELECT DISTINCT family_id FROM members WHERE household_id IS NULL")
    ).scalars().all()
    for family_id in family_ids:
        household_id = str(uuid.uuid4())
        bind.execute(
            sa.text("INSERT INTO households (id, family_id, name) VALUES (CAST(:hid AS uuid), CAST(:fid AS uuid), 'Main household')"),
            {"hid": household_id, "fid": str(family_id)},
        )
        bind.execute(
            sa.text("UPDATE members SET household_id = CAST(:hid AS uuid) WHERE family_id = CAST(:fid AS uuid) AND household_id IS NULL"),
            {"hid": household_id, "fid": str(family_id)},
        )

    # --- members: constraints (autogenerate cannot see these) ---
    op.execute("ALTER TABLE members DROP CONSTRAINT IF EXISTS check_adult_has_contact")
    op.execute("ALTER TABLE members DROP CONSTRAINT IF EXISTS check_phone_format")
    op.create_check_constraint(
        'check_password_needs_contact', 'members',
        'hashed_password IS NULL OR phone_number IS NOT NULL OR email IS NOT NULL',
    )
    op.create_check_constraint(
        'check_invite_contact_minors_only', 'members',
        'invite_contact IS NULL OR date_of_birth IS NOT NULL',
    )
    op.create_check_constraint(
        'check_phone_format', 'members',
        r"phone_number IS NULL OR phone_number ~ '^\+254[17][0-9]{8}$'",
    )

    # --- members: household_id becomes required, FK becomes RESTRICT ---
    op.alter_column('members', 'household_id', existing_type=sa.UUID(), nullable=False)
    op.drop_constraint('members_household_id_fkey', 'members', type_='foreignkey')
    op.create_foreign_key('members_household_id_fkey', 'members', 'households', ['household_id'], ['id'], ondelete='RESTRICT')

    # --- members: old columns removed ---
    op.drop_column('members', 'password_expires_at')
    op.drop_column('members', 'is_minor')
    op.drop_column('members', 'must_change_password')

    # --- audit_logs: widen the allowed actions / entity types ---
    op.drop_constraint('chk_audit_action', 'audit_logs', type_='check')
    op.drop_constraint('chk_audit_entity_type', 'audit_logs', type_='check')
    op.create_check_constraint('chk_audit_action', 'audit_logs', _in_list('action', NEW_AUDIT_ACTIONS))
    op.create_check_constraint('chk_audit_entity_type', 'audit_logs', _in_list('entity_type', NEW_ENTITY_TYPES))

    # --- Seed the five roles (safe to re-run: skips any that exist) ---
    for name, description in ROLES:
        bind.execute(
            sa.text(
                "INSERT INTO roles (id, name, description) "
                "VALUES (CAST(:id AS uuid), :name, :description) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "name": name, "description": description},
        )


def downgrade() -> None:
    """Downgrade schema. Seeded roles and the 'Main household' rows are left in place."""
    # audit_logs constraints back to the old lists
    op.drop_constraint('chk_audit_action', 'audit_logs', type_='check')
    op.drop_constraint('chk_audit_entity_type', 'audit_logs', type_='check')
    op.create_check_constraint('chk_audit_action', 'audit_logs', _in_list('action', OLD_AUDIT_ACTIONS))
    op.create_check_constraint('chk_audit_entity_type', 'audit_logs', _in_list('entity_type', OLD_ENTITY_TYPES))

    # members: old columns back (defaults let existing rows satisfy NOT NULL)
    op.add_column('members', sa.Column('must_change_password', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('members', sa.Column('is_minor', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('members', sa.Column('password_expires_at', postgresql.TIMESTAMP(timezone=True), nullable=True))

    # members: household_id optional again, FK back to SET NULL
    op.drop_constraint('members_household_id_fkey', 'members', type_='foreignkey')
    op.create_foreign_key('members_household_id_fkey', 'members', 'households', ['household_id'], ['id'], ondelete='SET NULL')
    op.alter_column('members', 'household_id', existing_type=sa.UUID(), nullable=True)

    # members: constraints back
    op.drop_constraint('check_invite_contact_minors_only', 'members', type_='check')
    op.drop_constraint('check_password_needs_contact', 'members', type_='check')
    op.create_check_constraint(
        'check_adult_has_contact', 'members',
        'is_minor = True OR phone_number IS NOT NULL OR email IS NOT NULL',
    )

    op.drop_column('members', 'invite_contact')
    op.drop_column('members', 'date_of_birth')

    # households
    op.drop_constraint('check_household_not_own_parent', 'households', type_='check')
    op.drop_constraint('fk_households_parent_household', 'households', type_='foreignkey')
    op.drop_constraint('fk_households_head_member', 'households', type_='foreignkey')
    op.drop_index(op.f('ix_households_parent_household_id'), table_name='households')
    op.drop_column('households', 'parent_household_id')
    op.drop_column('households', 'head_member_id')

    # families
    op.drop_constraint('check_age_of_majority_range', 'families', type_='check')
    op.drop_column('families', 'age_of_majority')

    # tables
    op.drop_index(op.f('ix_activation_tokens_member_id'), table_name='activation_tokens')
    op.drop_table('activation_tokens')
    op.drop_table('registration_codes')