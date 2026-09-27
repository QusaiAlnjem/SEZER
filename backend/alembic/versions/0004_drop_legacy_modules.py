"""drop importers, purchase orders, logistics and the inventory qr column

Revision ID: 0004_drop_legacy_modules
Revises: 0003_payments_cascade
Create Date: 2026-09-05 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_drop_legacy_modules"
down_revision = "0003_payments_cascade"
branch_labels = None
depends_on = None


def upgrade():
    # Dependents of purchase_orders go first.
    op.drop_table("logistics_entries")
    op.drop_column("inventory_receipts", "po_id")
    op.drop_table("po_items")
    op.drop_table("purchase_orders")
    op.drop_table("importers")
    # QR scanning is gone; the column and its index go with it.
    op.drop_column("inventory_items", "qr")


def downgrade():
    op.add_column("inventory_items", sa.Column("qr", sa.String(), unique=True))
    op.create_index("ix_inventory_qr", "inventory_items", ["qr"])

    op.create_table(
        "importers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("country", sa.String()),
        sa.Column("whatsapp", sa.String()),
        sa.Column("email", sa.String()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("po_number", sa.String(), nullable=False, unique=True),
        sa.Column("importer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("importers.id"), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("expected_date", sa.Date()),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("fx_to_usd", sa.Numeric(14, 4), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.Column("whatsapp_sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft','sent','partially_received','received','cancelled')", name="po_status_ck"),
        sa.CheckConstraint("currency IN ('USD','SYP')", name="po_currency_ck"),
    )

    op.create_table(
        "po_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("po_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku", sa.String()),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(), server_default="m"),
        sa.Column("pack_size", sa.Numeric(14, 3), nullable=False, server_default="1"),
        sa.Column("stock_unit", sa.String()),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), sa.Computed("qty * unit_price", persisted=True)),
    )

    op.add_column(
        "inventory_receipts",
        sa.Column("po_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id")),
    )

    op.create_table(
        "logistics_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("po_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id")),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("carrier", sa.String()),
        sa.Column("reference", sa.String()),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("fx_to_usd", sa.Numeric(14, 4), nullable=False),
        sa.Column("paid_at", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint("entry_type IN ('freight','remittance','duty','insurance','clearance','other')", name="log_type_ck"),
        sa.CheckConstraint("currency IN ('USD','SYP')", name="log_currency_ck"),
    )
