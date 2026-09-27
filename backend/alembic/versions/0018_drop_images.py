"""drop product and supplier photos

The picture features are gone from the app. Images were the only thing that
could realistically exhaust the object-storage quota — rows are tiny by
comparison — and nothing ever deleted them, so the bucket only grew.

Document uploads (Excel packing lists, PDFs) are untouched: they are how
receipts get imported.

Revision ID: 0018_drop_images
Revises: 0017_named_identity_only
Create Date: 2026-09-22 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_drop_images"
down_revision = "0017_named_identity_only"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("inventory_items", "image_path")
    op.drop_index("ix_supplier_photos_supplier", table_name="supplier_photos")
    op.drop_table("supplier_photos")


def downgrade():
    op.add_column("inventory_items", sa.Column("image_path", sa.String()))
    op.create_table(
        "supplier_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("description", sa.String()),
        sa.Column("uploaded_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_supplier_photos_supplier", "supplier_photos", ["supplier_id"])
