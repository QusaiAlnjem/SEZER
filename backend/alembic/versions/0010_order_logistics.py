"""shipping and customs on a sales order

Each is either a flat USD amount or a percentage of the products total.
`subtotal` keeps holding the full billed figure (products + logistics) so
payments, customer balances and the printed invoice all agree.

Revision ID: 0010_order_logistics
Revises: 0009_drop_sales_currency
Create Date: 2026-09-13 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_order_logistics"
down_revision = "0009_drop_sales_currency"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sales_orders",
                  sa.Column("shipping_value", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.add_column("sales_orders",
                  sa.Column("shipping_is_percent", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("sales_orders",
                  sa.Column("customs_value", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.add_column("sales_orders",
                  sa.Column("customs_is_percent", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    for col in ("customs_is_percent", "customs_value", "shipping_is_percent", "shipping_value"):
        op.drop_column("sales_orders", col)
