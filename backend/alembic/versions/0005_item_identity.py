"""rebuild inventory items around reference / quality / shade / colour

Revision ID: 0005_item_identity
Revises: 0004_drop_legacy_modules
Create Date: 2026-09-07 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_item_identity"
down_revision = "0004_drop_legacy_modules"
branch_labels = None
depends_on = None


def upgrade():
    # --- new identity columns ---
    op.add_column("inventory_items", sa.Column("reference", sa.String()))
    op.add_column("inventory_items", sa.Column("quality", sa.String()))
    op.add_column("inventory_items", sa.Column("color", sa.String()))
    op.add_column("inventory_items", sa.Column("shade", sa.String()))
    op.add_column("inventory_items", sa.Column("image_path", sa.String()))

    # Carry any existing rows over from the codes they used to be keyed by,
    # so the NOT NULL below can't fail on a populated table.
    op.execute(
        "UPDATE inventory_items "
        "SET reference = COALESCE(NULLIF(sku, ''), NULLIF(barcode, ''), id::text) "
        "WHERE reference IS NULL"
    )
    op.execute(
        "UPDATE inventory_items "
        "SET quality = COALESCE(NULLIF(sku, ''), NULLIF(name, ''), reference) "
        "WHERE quality IS NULL"
    )
    op.execute("UPDATE inventory_items SET unit = 'm' WHERE unit IS NULL OR unit = ''")

    op.alter_column("inventory_items", "reference", nullable=False)
    op.alter_column("inventory_items", "quality", nullable=False)
    op.alter_column("inventory_items", "unit", nullable=False, server_default="m")
    # الاسم is optional now — only reference, quality and quantity are required
    op.alter_column("inventory_items", "name", nullable=True)
    # alert threshold left the form; it defaults by unit (100 m / 10 pcs)
    op.alter_column("inventory_items", "reorder_level", server_default="100")

    # --- retire the old code columns (their unique constraints go with them) ---
    for col in ("sku", "barcode", "serial", "description", "location"):
        op.drop_column("inventory_items", col)

    op.create_index("ix_inventory_reference", "inventory_items", ["reference"])
    op.create_index("ix_inventory_quality", "inventory_items", ["quality"])
    # One reference ships in many shades, so identity is the whole tuple.
    # COALESCE keeps the two nullable halves comparable.
    op.execute(
        "CREATE UNIQUE INDEX uq_inventory_identity ON inventory_items "
        "(reference, quality, COALESCE(shade, ''), COALESCE(color, ''))"
    )

    # --- receipt lines: pack sizing is gone from the form ---
    op.drop_column("inventory_receipt_items", "pack_size")
    op.drop_column("inventory_receipt_items", "pack_unit")


def downgrade():
    op.add_column(
        "inventory_receipt_items",
        sa.Column("pack_size", sa.Numeric(14, 3), nullable=False, server_default="1"),
    )
    op.add_column("inventory_receipt_items", sa.Column("pack_unit", sa.String()))

    op.execute("DROP INDEX IF EXISTS uq_inventory_identity")
    op.drop_index("ix_inventory_quality", table_name="inventory_items")
    op.drop_index("ix_inventory_reference", table_name="inventory_items")

    op.add_column("inventory_items", sa.Column("sku", sa.String(), unique=True))
    op.add_column("inventory_items", sa.Column("barcode", sa.String(), unique=True))
    op.add_column("inventory_items", sa.Column("serial", sa.String(), unique=True))
    op.add_column("inventory_items", sa.Column("description", sa.Text()))
    op.add_column("inventory_items", sa.Column("location", sa.String()))
    op.create_index("ix_inventory_barcode", "inventory_items", ["barcode"])
    op.create_index("ix_inventory_serial", "inventory_items", ["serial"])

    op.execute("UPDATE inventory_items SET name = reference WHERE name IS NULL")
    op.alter_column("inventory_items", "name", nullable=False)
    op.alter_column("inventory_items", "reorder_level", server_default="0")
    op.alter_column("inventory_items", "unit", nullable=True, server_default="m")

    for col in ("image_path", "shade", "color", "quality", "reference"):
        op.drop_column("inventory_items", col)
