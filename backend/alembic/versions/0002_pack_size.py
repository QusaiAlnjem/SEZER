"""add pack_size / stock_unit / pack_unit

Revision ID: 0002_pack_size
Revises: 0001_init
Create Date: 2026-09-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_pack_size"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("po_items",
        sa.Column("pack_size", sa.Numeric(14, 3), nullable=False, server_default="1"))
    op.add_column("po_items",
        sa.Column("stock_unit", sa.String(), nullable=True))
    op.add_column("inventory_receipt_items",
        sa.Column("pack_size", sa.Numeric(14, 3), nullable=False, server_default="1"))
    op.add_column("inventory_receipt_items",
        sa.Column("pack_unit", sa.String(), nullable=True))


def downgrade():
    op.drop_column("inventory_receipt_items", "pack_unit")
    op.drop_column("inventory_receipt_items", "pack_size")
    op.drop_column("po_items", "stock_unit")
    op.drop_column("po_items", "pack_size")