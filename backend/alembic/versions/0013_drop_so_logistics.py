"""drop shipping and customs from sales orders

They were captured but never billed — `subtotal` has always been the products
total alone. Logistics now live on the purchase order (migration 0012), where
the money is actually spent, so these columns have no remaining purpose.

Revision ID: 0013_drop_so_logistics
Revises: 0012_po_costs
Create Date: 2026-09-21 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_drop_so_logistics"
down_revision = "0012_po_costs"
branch_labels = None
depends_on = None


def upgrade():
    for col in ("customs_is_percent", "customs_value", "shipping_is_percent", "shipping_value"):
        op.drop_column("sales_orders", col)


def downgrade():
    op.add_column("sales_orders",
                  sa.Column("shipping_value", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.add_column("sales_orders",
                  sa.Column("shipping_is_percent", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("sales_orders",
                  sa.Column("customs_value", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.add_column("sales_orders",
                  sa.Column("customs_is_percent", sa.Boolean(), nullable=False, server_default=sa.false()))
