"""remember which packing lists have been imported

Imported rows carry no name, so they can never match an existing item and
cannot be deduplicated on identity. Re-importing the same list therefore
doubles every quantity in silence. Recording a fingerprint of each import's
contents lets a repeat be recognised and questioned.

Revision ID: 0021_import_fingerprints
Revises: 0020_selling_price
Create Date: 2026-09-27 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021_import_fingerprints"
down_revision = "0020_selling_price"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "spreadsheet_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  primary_key=True, server_default=sa.text("gen_random_uuid()")),
        # sha256 of the parsed rows, so a re-saved file with identical contents
        # is still recognised
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("inventory_receipts.id", ondelete="SET NULL")),
        sa.Column("rows_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_spreadsheet_imports_fingerprint",
                    "spreadsheet_imports", ["fingerprint"])


def downgrade():
    op.drop_index("ix_spreadsheet_imports_fingerprint", table_name="spreadsheet_imports")
    op.drop_table("spreadsheet_imports")
