"""total shipment cost on a supplier order

One USD total for the whole shipment. Informational only — it is deliberately
kept out of inventory_items.avg_unit_cost_usd and the per-line receipt costs,
which have their own numbers.

Revision ID: 0008_shipment_cost
Revises: 0007_suppliers
Create Date: 2026-09-09 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_shipment_cost"
down_revision = "0007_suppliers"
branch_labels = None
depends_on = None


def upgrade():
    # nullable: recording the cost is always optional
    op.add_column("supplier_orders", sa.Column("shipment_cost", sa.Numeric(14, 2)))


def downgrade():
    op.drop_column("supplier_orders", "shipment_cost")
