"""selling price per item, separate from cost

`avg_unit_cost_usd` is what the goods cost — calculated from purchase orders and
left alone. `selling_price` is what a unit sells for: $1 until the product has
actually sold, then the most recent sale price, inherited by a matching product
the next time one is added.

Revision ID: 0020_selling_price
Revises: 0019_drop_documents
Create Date: 2026-09-27 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_selling_price"
down_revision = "0019_drop_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "inventory_items",
        sa.Column("selling_price", sa.Numeric(14, 4), nullable=False, server_default="1"),
    )
    # Seed from history: whatever each item last actually sold for.
    op.execute("""
        UPDATE inventory_items i
           SET selling_price = latest.unit_price
        FROM (
            SELECT DISTINCT ON (li.inventory_item_id)
                   li.inventory_item_id, li.unit_price
            FROM sales_order_items li
            JOIN sales_orders so ON so.id = li.sales_order_id
            ORDER BY li.inventory_item_id, so.order_date DESC, so.created_at DESC
        ) AS latest
        WHERE latest.inventory_item_id = i.id
    """)


def downgrade():
    op.drop_column("inventory_items", "selling_price")
