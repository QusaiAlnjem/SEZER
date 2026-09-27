"""item identity moves to (name, quality, colour, shade); invoice discount

Identity no longer keys off `reference`: two lines are the same product when
the name, the طراز and the colour/shade agree. The name is stored stripped, so
stray spaces can't split one product into two rows.

Also adds `discount` to sales orders — `subtotal` stays the billed figure, now
net of it.

Revision ID: 0016_identity_and_discount
Revises: 0015_logistics_per_unit
Create Date: 2026-09-22 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_identity_and_discount"
down_revision = "0015_logistics_per_unit"
branch_labels = None
depends_on = None


def upgrade():
    # tidy any stray whitespace before the new index has to trust the column
    op.execute(
        "UPDATE inventory_items "
        "SET name = NULLIF(regexp_replace(btrim(name), '\\s+', ' ', 'g'), '') "
        "WHERE name IS NOT NULL"
    )
    op.execute("DROP INDEX IF EXISTS uq_inventory_identity")
    op.execute(
        "CREATE UNIQUE INDEX uq_inventory_identity ON inventory_items "
        "(COALESCE(name, ''), quality, COALESCE(shade, ''), COALESCE(color, ''))"
    )

    op.add_column("sales_orders",
                  sa.Column("discount", sa.Numeric(14, 2), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("sales_orders", "discount")
    op.execute("DROP INDEX IF EXISTS uq_inventory_identity")
    op.execute(
        "CREATE UNIQUE INDEX uq_inventory_identity ON inventory_items "
        "(reference, quality, COALESCE(shade, ''), COALESCE(color, ''))"
    )
