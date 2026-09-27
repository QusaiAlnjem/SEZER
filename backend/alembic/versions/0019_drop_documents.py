"""stop storing uploaded spreadsheets

A packing list is parsed into receipt lines and then discarded. Once those rows
exist the file holds nothing the database doesn't, and nothing ever read one
back — the download endpoint was never called. Keeping them only consumed the
object-storage quota, forever, since nothing deleted them either.

With this, no part of the app writes to Supabase Storage at all.

Revision ID: 0019_drop_documents
Revises: 0018_drop_images
Create Date: 2026-09-27 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019_drop_documents"
down_revision = "0018_drop_images"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("inventory_documents")


def downgrade():
    op.create_table(
        "inventory_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("inventory_receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String()),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("parsed", sa.Boolean(), server_default=sa.false()),
        sa.Column("uploaded_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
