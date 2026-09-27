"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-08-31 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(), nullable=False, unique=True, server_default="owner"),
        sa.Column("pin_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "fx_rates",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date, nullable=False, unique=True),
        sa.Column("syp_per_usd", sa.Numeric(14, 4), nullable=False),
        sa.Column("source", sa.String(), server_default="manual"),
    )

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
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String()),
        sa.Column("city", sa.String()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "inventory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sku", sa.String(), unique=True),
        sa.Column("barcode", sa.String(), unique=True),
        sa.Column("qr", sa.String(), unique=True),
        sa.Column("serial", sa.String(), unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("unit", sa.String(), server_default="m"),
        sa.Column("qty_on_hand", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("avg_unit_cost_usd", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("reorder_level", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("location", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_inventory_barcode", "inventory_items", ["barcode"])
    op.create_index("ix_inventory_qr", "inventory_items", ["qr"])
    op.create_index("ix_inventory_serial", "inventory_items", ["serial"])

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
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), sa.Computed("qty * unit_price", persisted=True)),
    )

    op.create_table(
        "sales_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_number", sa.String(), nullable=False, unique=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("fx_to_usd", sa.Numeric(14, 4), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('open','partial','paid','cancelled')", name="so_status_ck"),
        sa.CheckConstraint("currency IN ('USD','SYP')", name="so_currency_ck"),
    )

    op.create_table(
        "sales_order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_items.id"), nullable=False),
        sa.Column("qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), sa.Computed("qty * unit_price", persisted=True)),
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("paid_at", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("fx_to_usd", sa.Numeric(14, 4), nullable=False),
        sa.Column("method", sa.String(), server_default="cash"),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint("currency IN ('USD','SYP')", name="pay_currency_ck"),
        sa.CheckConstraint("method IN ('cash','bank','remittance','other')", name="pay_method_ck"),
    )

    op.create_table(
        "inventory_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("po_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id")),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("received_by", sa.String()),
        sa.Column("notes", sa.Text()),
    )

    op.create_table(
        "inventory_receipt_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_items.id"), nullable=False),
        sa.Column("qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("fx_to_usd", sa.Numeric(14, 4), nullable=False),
        sa.CheckConstraint("currency IN ('USD','SYP')", name="rcpt_currency_ck"),
    )

    op.create_table(
        "inventory_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String()),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("parsed", sa.Boolean(), server_default=sa.false()),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
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

    op.create_table(
        "expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("fx_to_usd", sa.Numeric(14, 4), nullable=False),
        sa.Column("spent_at", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint("currency IN ('USD','SYP')", name="exp_currency_ck"),
    )


def downgrade():
    for t in (
        "expenses", "logistics_entries", "inventory_documents", "inventory_receipt_items",
        "inventory_receipts", "payments", "sales_order_items", "sales_orders",
        "po_items", "purchase_orders", "inventory_items", "customers",
        "importers", "fx_rates", "users",
    ):
        op.drop_table(t)
