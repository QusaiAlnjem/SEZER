"""shipping and customs on a purchase order

`shipment_cost` keeps its meaning — the goods total. These two sit beside it,
each either a flat USD amount or a percentage of that goods total, mirroring
how sales_orders already stores its logistics lines.

Revision ID: 0012_po_costs
Revises: 0011_po_product_shade
Create Date: 2026-09-16 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_po_costs"
down_revision = "0011_po_product_shade"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("supplier_orders",
                  sa.Column("shipping_value", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.add_column("supplier_orders",
                  sa.Column("shipping_is_percent", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("supplier_orders",
                  sa.Column("customs_value", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.add_column("supplier_orders",
                  sa.Column("customs_is_percent", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    for col in ("customs_is_percent", "customs_value", "shipping_is_percent", "shipping_value"):
        op.drop_column("supplier_orders", col)
