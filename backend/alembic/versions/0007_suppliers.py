"""suppliers, their product photos, and supplier orders

Revision ID: 0007_suppliers
Revises: 0006_receipt_item_cascade
Create Date: 2026-09-09 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_suppliers"
down_revision = "0006_receipt_item_cascade"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("company_name", sa.String()),
        sa.Column("phones", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("email", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_suppliers_name", "suppliers", ["name"])

    op.create_table(
        "supplier_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("description", sa.String()),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_supplier_photos_supplier", "supplier_photos", ["supplier_id"])

    op.create_table(
        "supplier_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_number", sa.String(), nullable=False, unique=True),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("shipping_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="waiting"),
        sa.Column("shipped_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('waiting','shipped')", name="supplier_order_status_ck"),
    )
    op.create_index("ix_supplier_orders_supplier", "supplier_orders", ["supplier_id"])
    op.create_index("ix_supplier_orders_status", "supplier_orders", ["status"])

    op.create_table(
        "supplier_order_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("supplier_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String()),
        sa.Column("quality", sa.String()),
        sa.Column("color", sa.String()),
    )
    op.create_index("ix_supplier_order_products_order", "supplier_order_products", ["order_id"])

    # "received by" was written but never displayed anywhere; the slot now holds
    # the order this delivery fulfils.
    op.drop_column("inventory_receipts", "received_by")
    op.add_column(
        "inventory_receipts",
        sa.Column("supplier_order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("supplier_orders.id", ondelete="SET NULL")),
    )


def downgrade():
    op.drop_column("inventory_receipts", "supplier_order_id")
    op.add_column("inventory_receipts", sa.Column("received_by", sa.String()))
    op.drop_table("supplier_order_products")
    op.drop_table("supplier_orders")
    op.drop_table("supplier_photos")
    op.drop_table("suppliers")
