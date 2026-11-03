"""contributions parts 2 to 4: payments, fines, welfare fund, events, expenses

Revision ID: b52d8e1f6c31
Revises: a41c7d9e5b20
Create Date: 2026-10-24

Hand-written (autogenerate does not see CHECK constraint changes).
  pledges              + check: paid amount never exceeds the pledge
  pledge_installments  + unique due date per pledge, positive amount
  payments             + family_id, fine_id, paid_by, recorded_by, confirmed_at, void and reject fields;
                         exactly one target; idempotency key unique per family
  fines                + family_id, financial_year_id, standing_fund_id, recorded_by, paid amount, status, void fields
  standing_funds       one per family; balance never negative
  events               + budget_amount, status
  campaign_events      + allocated_amount
  expenses             + description, status, approval, void and reject fields; exactly one source

payments, fines and expenses had no endpoints before this migration, so they must
be empty. If they contain rows the migration stops with a message and changes
nothing (PostgreSQL DDL is transactional).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b52d8e1f6c31"
down_revision: Union[str, Sequence[str], None] = "a41c7d9e5b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _count(bind, sql: str) -> int:
    return bind.execute(sa.text(sql)).scalar() or 0


def upgrade() -> None:
    bind = op.get_bind()

    # ---- Guards ----
    for table in ("payments", "fines", "expenses"):
        if _count(bind, f"SELECT count(*) FROM {table}"):
            raise RuntimeError(
                f"The {table} table already has rows. It had no endpoints before this migration, "
                "so it should be empty. Tell Claude what is in it before going on."
            )
    if _count(bind, "SELECT count(*) FROM (SELECT family_id FROM standing_funds GROUP BY family_id HAVING count(*) > 1) t"):
        raise RuntimeError("Some families have more than one standing fund. Keep one per family, then run again.")
    if _count(bind, "SELECT count(*) FROM standing_funds WHERE balance < 0"):
        raise RuntimeError("A standing fund has a negative balance. Fix it, then run again.")
    if _count(bind, "SELECT count(*) FROM pledges WHERE fulfilled_amount > amount"):
        raise RuntimeError("Some pledges have fulfilled_amount above amount. Fix them, then run again.")

    # ---- pledges ----
    op.create_check_constraint("check_pledge_fulfilled_within_amount", "pledges", "fulfilled_amount <= amount")

    # ---- pledge_installments ----
    op.create_check_constraint("check_installment_amount_positive", "pledge_installments", "amount > 0")
    op.create_unique_constraint(
        "uq_installment_pledge_due_date", "pledge_installments", ["pledge_id", "due_date"]
    )

    # ---- standing_funds ----
    op.create_unique_constraint("uq_standing_fund_family", "standing_funds", ["family_id"])
    op.create_check_constraint("check_standing_fund_balance_not_negative", "standing_funds", "balance >= 0")

    # ---- events and campaign_events ----
    op.add_column("events", sa.Column("budget_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("events", sa.Column("status", sa.String(), nullable=False, server_default="planned"))
    op.alter_column("events", "status", server_default=None)
    op.create_check_constraint(
        "check_event_budget_positive", "events", "budget_amount IS NULL OR budget_amount > 0"
    )
    op.add_column("campaign_events", sa.Column("allocated_amount", sa.Numeric(12, 2), nullable=True))
    op.create_check_constraint(
        "check_campaign_event_allocation_positive", "campaign_events",
        "allocated_amount IS NULL OR allocated_amount > 0",
    )

    # ---- fines (empty) ----
    op.add_column("fines", sa.Column("family_id", sa.UUID(), nullable=False))
    op.add_column("fines", sa.Column("financial_year_id", sa.UUID(), nullable=False))
    op.add_column("fines", sa.Column("standing_fund_id", sa.UUID(), nullable=False))
    op.add_column("fines", sa.Column("recorded_by", sa.UUID(), nullable=False))
    op.add_column("fines", sa.Column("fulfilled_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("fines", sa.Column("status", sa.String(), nullable=False, server_default="unpaid"))
    op.add_column("fines", sa.Column("waive_reason", sa.String(length=300), nullable=True))
    op.add_column("fines", sa.Column("voided_by", sa.UUID(), nullable=True))
    op.add_column("fines", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("fines", sa.Column("void_reason", sa.String(length=300), nullable=True))
    op.add_column(
        "fines",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.alter_column("fines", "fulfilled_amount", server_default=None)
    op.alter_column("fines", "status", server_default=None)
    op.create_foreign_key("fk_fines_family_id", "fines", "families", ["family_id"], ["id"])
    op.create_foreign_key("fk_fines_financial_year_id", "fines", "financial_years", ["financial_year_id"], ["id"])
    op.create_foreign_key("fk_fines_standing_fund_id", "fines", "standing_funds", ["standing_fund_id"], ["id"])
    op.create_foreign_key("fk_fines_recorded_by", "fines", "members", ["recorded_by"], ["id"])
    op.create_foreign_key("fk_fines_voided_by", "fines", "members", ["voided_by"], ["id"])
    op.create_index("ix_fines_family_id", "fines", ["family_id"])
    op.create_index("ix_fines_financial_year_id", "fines", ["financial_year_id"])
    op.create_check_constraint("check_fine_amount_positive", "fines", "amount > 0")
    op.create_check_constraint(
        "check_fine_fulfilled_range", "fines", "fulfilled_amount >= 0 AND fulfilled_amount <= amount"
    )

    # ---- payments (empty) ----
    op.add_column("payments", sa.Column("family_id", sa.UUID(), nullable=False))
    op.add_column("payments", sa.Column("fine_id", sa.UUID(), nullable=True))
    op.add_column("payments", sa.Column("paid_by", sa.UUID(), nullable=False))
    op.add_column("payments", sa.Column("recorded_by", sa.UUID(), nullable=False))
    op.add_column("payments", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("reject_reason", sa.String(length=300), nullable=True))
    op.add_column("payments", sa.Column("voided_by", sa.UUID(), nullable=True))
    op.add_column("payments", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("void_reason", sa.String(length=300), nullable=True))
    op.create_foreign_key("fk_payments_family_id", "payments", "families", ["family_id"], ["id"])
    op.create_foreign_key("fk_payments_fine_id", "payments", "fines", ["fine_id"], ["id"])
    op.create_foreign_key("fk_payments_paid_by", "payments", "members", ["paid_by"], ["id"])
    op.create_foreign_key("fk_payments_recorded_by", "payments", "members", ["recorded_by"], ["id"])
    op.create_foreign_key("fk_payments_voided_by", "payments", "members", ["voided_by"], ["id"])
    op.create_index("ix_payments_family_id", "payments", ["family_id"])
    op.create_index("ix_payments_fine_id", "payments", ["fine_id"])
    # The idempotency key was unique across the whole platform. It becomes unique per family.
    op.execute("ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_idempotency_key_key")
    op.create_unique_constraint(
        "uq_payment_family_idempotency", "payments", ["family_id", "idempotency_key"]
    )
    op.create_check_constraint(
        "check_payment_one_target", "payments",
        "(pledge_id IS NOT NULL)::int + (fine_id IS NOT NULL)::int + (standing_fund_id IS NOT NULL)::int = 1",
    )
    op.create_check_constraint("check_payment_amount_positive", "payments", "amount > 0")

    # ---- expenses (empty) ----
    op.add_column("expenses", sa.Column("description", sa.String(length=200), nullable=True))
    op.add_column("expenses", sa.Column("status", sa.String(), nullable=False, server_default="pending"))
    op.add_column("expenses", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("expenses", sa.Column("reject_reason", sa.String(length=300), nullable=True))
    op.add_column("expenses", sa.Column("voided_by", sa.UUID(), nullable=True))
    op.add_column("expenses", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("expenses", sa.Column("void_reason", sa.String(length=300), nullable=True))
    op.add_column(
        "expenses",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.alter_column("expenses", "status", server_default=None)
    op.create_foreign_key("fk_expenses_voided_by", "expenses", "members", ["voided_by"], ["id"])
    op.create_check_constraint(
        "check_expense_one_source", "expenses",
        "(event_id IS NOT NULL)::int + (standing_fund_id IS NOT NULL)::int = 1",
    )
    op.create_check_constraint("check_expense_amount_positive", "expenses", "amount > 0")


def downgrade() -> None:
    # expenses
    op.drop_constraint("check_expense_amount_positive", "expenses", type_="check")
    op.drop_constraint("check_expense_one_source", "expenses", type_="check")
    op.drop_constraint("fk_expenses_voided_by", "expenses", type_="foreignkey")
    for column in ("created_at", "void_reason", "voided_at", "voided_by", "reject_reason",
                   "approved_at", "status", "description"):
        op.drop_column("expenses", column)

    # payments
    op.drop_constraint("check_payment_amount_positive", "payments", type_="check")
    op.drop_constraint("check_payment_one_target", "payments", type_="check")
    op.drop_constraint("uq_payment_family_idempotency", "payments", type_="unique")
    op.create_unique_constraint("payments_idempotency_key_key", "payments", ["idempotency_key"])
    op.drop_index("ix_payments_fine_id", table_name="payments")
    op.drop_index("ix_payments_family_id", table_name="payments")
    op.drop_constraint("fk_payments_voided_by", "payments", type_="foreignkey")
    op.drop_constraint("fk_payments_recorded_by", "payments", type_="foreignkey")
    op.drop_constraint("fk_payments_paid_by", "payments", type_="foreignkey")
    op.drop_constraint("fk_payments_fine_id", "payments", type_="foreignkey")
    op.drop_constraint("fk_payments_family_id", "payments", type_="foreignkey")
    for column in ("void_reason", "voided_at", "voided_by", "reject_reason", "confirmed_at",
                   "recorded_by", "paid_by", "fine_id", "family_id"):
        op.drop_column("payments", column)

    # fines
    op.drop_constraint("check_fine_fulfilled_range", "fines", type_="check")
    op.drop_constraint("check_fine_amount_positive", "fines", type_="check")
    op.drop_index("ix_fines_financial_year_id", table_name="fines")
    op.drop_index("ix_fines_family_id", table_name="fines")
    op.drop_constraint("fk_fines_voided_by", "fines", type_="foreignkey")
    op.drop_constraint("fk_fines_recorded_by", "fines", type_="foreignkey")
    op.drop_constraint("fk_fines_standing_fund_id", "fines", type_="foreignkey")
    op.drop_constraint("fk_fines_financial_year_id", "fines", type_="foreignkey")
    op.drop_constraint("fk_fines_family_id", "fines", type_="foreignkey")
    for column in ("created_at", "void_reason", "voided_at", "voided_by", "waive_reason", "status",
                   "fulfilled_amount", "recorded_by", "standing_fund_id", "financial_year_id", "family_id"):
        op.drop_column("fines", column)

    # events and campaign_events
    op.drop_constraint("check_campaign_event_allocation_positive", "campaign_events", type_="check")
    op.drop_column("campaign_events", "allocated_amount")
    op.drop_constraint("check_event_budget_positive", "events", type_="check")
    op.drop_column("events", "status")
    op.drop_column("events", "budget_amount")

    # standing_funds
    op.drop_constraint("check_standing_fund_balance_not_negative", "standing_funds", type_="check")
    op.drop_constraint("uq_standing_fund_family", "standing_funds", type_="unique")

    # pledge_installments and pledges
    op.drop_constraint("uq_installment_pledge_due_date", "pledge_installments", type_="unique")
    op.drop_constraint("check_installment_amount_positive", "pledge_installments", type_="check")
    op.drop_constraint("check_pledge_fulfilled_within_amount", "pledges", type_="check")