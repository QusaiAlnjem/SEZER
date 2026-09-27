"""كشف حساب — an issued customer account statement

Stores only the number and the window it covers. The figures on it are
recomputed from orders and payments on every view, as invoices already are.

Revision ID: 0014_account_statements
Revises: 0013_drop_so_logistics
Create Date: 2026-09-21 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_account_statements"
down_revision = "0013_drop_so_logistics"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account_statements",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("statement_number", sa.String(), nullable=False, unique=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_account_statements_customer", "account_statements", ["customer_id"])


def downgrade():
    op.drop_index("ix_account_statements_customer", table_name="account_statements")
    op.drop_table("account_statements")
