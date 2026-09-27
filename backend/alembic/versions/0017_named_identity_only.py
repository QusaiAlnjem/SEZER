"""identity applies only to named items

An empty name is not evidence of sameness: two different fabrics can share a
طراز, colour and درجة and be told apart only by name. So a nameless row is
never matched to anything, and the uniqueness rule has to step aside for it —
otherwise the index would refuse the second nameless row it is meant to allow.

Revision ID: 0017_named_identity_only
Revises: 0016_identity_and_discount
Create Date: 2026-09-22 00:00:00
"""
from alembic import op

revision = "0017_named_identity_only"
down_revision = "0016_identity_and_discount"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP INDEX IF EXISTS uq_inventory_identity")
    op.execute(
        "CREATE UNIQUE INDEX uq_inventory_identity ON inventory_items "
        "(name, quality, COALESCE(shade, ''), COALESCE(color, '')) "
        "WHERE name IS NOT NULL"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_inventory_identity")
    op.execute(
        "CREATE UNIQUE INDEX uq_inventory_identity ON inventory_items "
        "(COALESCE(name, ''), quality, COALESCE(shade, ''), COALESCE(color, ''))"
    )
