"""drop currency/fx from sales orders and payments

The creditors flow is USD-only, so `currency` was pinned to 'USD' and
`fx_to_usd` to 1 on every row. fx only exists to convert away from USD, so it
goes with the currency rather than being left behind as a meaningless 1.

Expenses and fx_rates are untouched — they still record SYP.

Revision ID: 0009_drop_sales_currency
Revises: 0008_shipment_cost
Create Date: 2026-09-12 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_drop_sales_currency"
down_revision = "0008_shipment_cost"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("so_currency_ck", "sales_orders", type_="check")
    op.drop_column("sales_orders", "currency")
    op.drop_column("sales_orders", "fx_to_usd")

    op.drop_constraint("pay_currency_ck", "payments", type_="check")
    op.drop_column("payments", "currency")
    op.drop_column("payments", "fx_to_usd")


def downgrade():
    op.add_column("sales_orders",
                  sa.Column("currency", sa.String(), nullable=False, server_default="USD"))
    op.add_column("sales_orders",
                  sa.Column("fx_to_usd", sa.Numeric(14, 4), nullable=False, server_default="1"))
    op.create_check_constraint("so_currency_ck", "sales_orders", "currency IN ('USD','SYP')")

    op.add_column("payments",
                  sa.Column("currency", sa.String(), nullable=False, server_default="USD"))
    op.add_column("payments",
                  sa.Column("fx_to_usd", sa.Numeric(14, 4), nullable=False, server_default="1"))
    op.create_check_constraint("pay_currency_ck", "payments", "currency IN ('USD','SYP')")
