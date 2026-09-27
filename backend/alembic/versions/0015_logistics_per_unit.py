"""how much of an item's unit cost is shipping + customs

Set when a purchase order's costs are spread across what it delivered, so the
item form can tell the user what the logistics share was before they adjust
the price. Null means no purchase order ever costed this item.

Revision ID: 0015_logistics_per_unit
Revises: 0014_account_statements
Create Date: 2026-09-21 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_logistics_per_unit"
down_revision = "0014_account_statements"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("inventory_items", sa.Column("logistics_per_unit", sa.Numeric(14, 4)))


def downgrade():
    op.drop_column("inventory_items", "logistics_per_unit")
