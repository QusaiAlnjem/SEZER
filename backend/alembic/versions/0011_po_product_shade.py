"""shade on a purchase-order product

Mirrors inventory_items.shade (رقم الطيف): one reference ships in several
shades, so a PO line names the shade alongside the colour.

Revision ID: 0011_po_product_shade
Revises: 0010_order_logistics
Create Date: 2026-09-16 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_po_product_shade"
down_revision = "0010_order_logistics"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("supplier_order_products", sa.Column("shade", sa.String()))


def downgrade():
    op.drop_column("supplier_order_products", "shade")
