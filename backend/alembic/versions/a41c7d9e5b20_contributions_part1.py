"""contributions part 1: financial years, campaigns, rules, pledges

Revision ID: a41c7d9e5b20
Revises: 083676136bab
Create Date: 2026-10-21

Hand-written (autogenerate does not see CHECK constraint changes or data
backfills). Changes:
  financial_years      + start_date, end_date, status; overlap-free dates; unique label per family
  campaigns            + name, created_by; checks on dates and target
  contribution_rules   cash_amount becomes required; unique category per campaign
  pledges              + family_id, pledged_by, source, status; unique member per campaign
  audit_logs           widen the allowed actions and entity types for the whole contributions feature

Existing rows are backfilled where a sensible value exists. If a rule or a
duplicate makes the change impossible, the migration stops with a message and
changes nothing (PostgreSQL DDL is transactional).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a41c7d9e5b20"
down_revision: Union[str, Sequence[str], None] = "083676136bab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copies: a migration must not import from app code.
PREVIOUS_AUDIT_ACTIONS = (
    "create", "update", "delete", "deactivate_member", "reset_password",
    "register_family", "send_invite", "activate_member", "login",
    "change_password", "view_date_of_birth", "change_household",
)
PREVIOUS_ENTITY_TYPES = ("member", "household", "contribution_rule", "family")

NEW_AUDIT_ACTIONS = PREVIOUS_AUDIT_ACTIONS + (
    "open_campaign", "close_campaign", "cancel_campaign",
    "confirm_payment", "reject_payment", "void_payment",
    "waive_fine", "void_fine",
    "approve_expense", "reject_expense", "void_expense",
    "close_financial_year",
)
NEW_ENTITY_TYPES = PREVIOUS_ENTITY_TYPES + (
    "financial_year", "campaign", "pledge", "payment",
    "fine", "expense", "event", "standing_fund",
)


def _in_list(column: str, values: tuple) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _scalar(bind, sql: str):
    return bind.execute(sa.text(sql)).scalar()


def upgrade() -> None:
    bind = op.get_bind()

    # ---- Guards: stop early with a clear message ----
    if _scalar(bind, "SELECT count(*) FROM campaigns WHERE type = 'standing'"):
        raise RuntimeError(
            "Some campaigns have type 'standing'. The welfare fund is now the standing_funds "
            "table, not a campaign type. Move or delete those rows, then run the migration again."
        )
    if _scalar(bind, "SELECT count(*) FROM contribution_rules WHERE cash_amount IS NULL OR cash_amount <= 0"):
        raise RuntimeError(
            "Some contribution_rules have no cash_amount (or zero). cash_amount is now required "
            "and is always the KES value. Fix those rows, then run the migration again."
        )

    # ---- financial_years ----
    op.add_column("financial_years", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("financial_years", sa.Column("end_date", sa.Date(), nullable=True))
    op.add_column("financial_years", sa.Column("status", sa.String(), nullable=False, server_default="open"))
    # Existing years become 1 January to 31 December of their label.
    op.execute("UPDATE financial_years SET start_date = make_date(year, 1, 1), end_date = make_date(year, 12, 31)")
    op.alter_column("financial_years", "start_date", nullable=False)
    op.alter_column("financial_years", "end_date", nullable=False)
    op.alter_column("financial_years", "status", server_default=None)
    op.create_check_constraint("check_financial_year_dates", "financial_years", "end_date > start_date")
    op.create_unique_constraint("uq_financial_year_family_year", "financial_years", ["family_id", "year"])

    # ---- campaigns ----
    op.add_column("campaigns", sa.Column("name", sa.String(length=100), nullable=True))
    op.execute("UPDATE campaigns SET name = 'Campaign ' || start_date::text WHERE name IS NULL")
    op.alter_column("campaigns", "name", nullable=False)
    op.add_column("campaigns", sa.Column("created_by", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_campaigns_created_by", "campaigns", "members", ["created_by"], ["id"])
    op.create_check_constraint("check_campaign_dates", "campaigns", "end_date >= start_date")
    op.create_check_constraint(
        "check_campaign_target_positive", "campaigns", "target_amount IS NULL OR target_amount > 0"
    )

    # ---- contribution_rules ----
    op.alter_column("contribution_rules", "cash_amount", existing_type=sa.Numeric(12, 2), nullable=False)
    op.alter_column(
        "contribution_rules", "member_category",
        existing_type=sa.String(), type_=sa.String(length=50), existing_nullable=False,
    )
    op.create_unique_constraint(
        "uq_rule_campaign_category", "contribution_rules", ["campaign_id", "member_category"]
    )
    op.create_check_constraint("check_rule_cash_positive", "contribution_rules", "cash_amount > 0")

    # ---- pledges ----
    op.add_column("pledges", sa.Column("family_id", sa.UUID(), nullable=True))
    op.add_column("pledges", sa.Column("pledged_by", sa.UUID(), nullable=True))
    op.add_column("pledges", sa.Column("source", sa.String(), nullable=False, server_default="voluntary"))
    op.add_column("pledges", sa.Column("status", sa.String(), nullable=False, server_default="active"))
    op.execute("UPDATE pledges SET family_id = (SELECT m.family_id FROM members m WHERE m.id = pledges.member_id)")
    op.execute("UPDATE pledges SET pledged_by = member_id WHERE pledged_by IS NULL")
    op.execute("UPDATE pledges SET status = 'fulfilled' WHERE fulfilled_amount >= amount")
    op.alter_column("pledges", "family_id", nullable=False)
    op.alter_column("pledges", "pledged_by", nullable=False)
    op.alter_column("pledges", "source", server_default=None)
    op.alter_column("pledges", "status", server_default=None)
    op.create_foreign_key("fk_pledges_family_id", "pledges", "families", ["family_id"], ["id"])
    op.create_foreign_key("fk_pledges_pledged_by", "pledges", "members", ["pledged_by"], ["id"])
    op.create_index("ix_pledges_family_id", "pledges", ["family_id"])
    op.create_unique_constraint("uq_pledge_member_campaign", "pledges", ["member_id", "campaign_id"])
    op.create_check_constraint("check_pledge_amount_positive", "pledges", "amount > 0")
    op.create_check_constraint("check_pledge_fulfilled_not_negative", "pledges", "fulfilled_amount >= 0")

    # ---- audit_logs: widen allowed actions and entity types ----
    op.drop_constraint("chk_audit_action", "audit_logs", type_="check")
    op.drop_constraint("chk_audit_entity_type", "audit_logs", type_="check")
    op.create_check_constraint("chk_audit_action", "audit_logs", _in_list("action", NEW_AUDIT_ACTIONS))
    op.create_check_constraint("chk_audit_entity_type", "audit_logs", _in_list("entity_type", NEW_ENTITY_TYPES))


def downgrade() -> None:
    # audit_logs back to the previous lists. This fails if audit rows with the
    # new actions exist; that is deliberate, because audit history must not be deleted.
    op.drop_constraint("chk_audit_action", "audit_logs", type_="check")
    op.drop_constraint("chk_audit_entity_type", "audit_logs", type_="check")
    op.create_check_constraint("chk_audit_action", "audit_logs", _in_list("action", PREVIOUS_AUDIT_ACTIONS))
    op.create_check_constraint("chk_audit_entity_type", "audit_logs", _in_list("entity_type", PREVIOUS_ENTITY_TYPES))

    # pledges
    op.drop_constraint("check_pledge_fulfilled_not_negative", "pledges", type_="check")
    op.drop_constraint("check_pledge_amount_positive", "pledges", type_="check")
    op.drop_constraint("uq_pledge_member_campaign", "pledges", type_="unique")
    op.drop_index("ix_pledges_family_id", table_name="pledges")
    op.drop_constraint("fk_pledges_pledged_by", "pledges", type_="foreignkey")
    op.drop_constraint("fk_pledges_family_id", "pledges", type_="foreignkey")
    op.drop_column("pledges", "status")
    op.drop_column("pledges", "source")
    op.drop_column("pledges", "pledged_by")
    op.drop_column("pledges", "family_id")

    # contribution_rules
    op.drop_constraint("check_rule_cash_positive", "contribution_rules", type_="check")
    op.drop_constraint("uq_rule_campaign_category", "contribution_rules", type_="unique")
    op.alter_column(
        "contribution_rules", "member_category",
        existing_type=sa.String(length=50), type_=sa.String(), existing_nullable=False,
    )
    op.alter_column("contribution_rules", "cash_amount", existing_type=sa.Numeric(12, 2), nullable=True)

    # campaigns
    op.drop_constraint("check_campaign_target_positive", "campaigns", type_="check")
    op.drop_constraint("check_campaign_dates", "campaigns", type_="check")
    op.drop_constraint("fk_campaigns_created_by", "campaigns", type_="foreignkey")
    op.drop_column("campaigns", "created_by")
    op.drop_column("campaigns", "name")

    # financial_years
    op.drop_constraint("uq_financial_year_family_year", "financial_years", type_="unique")
    op.drop_constraint("check_financial_year_dates", "financial_years", type_="check")
    op.drop_column("financial_years", "status")
    op.drop_column("financial_years", "end_date")
    op.drop_column("financial_years", "start_date")