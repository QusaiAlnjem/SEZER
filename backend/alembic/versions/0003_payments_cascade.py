"""payments.sales_order_id cascades on delete

Revision ID: 0003_payments_cascade
Revises: 0002_pack_size
Create Date: 2026-09-01 00:00:00
"""
from alembic import op

revision = "0003_payments_cascade"
down_revision = "0002_pack_size"
branch_labels = None
depends_on = None


def upgrade():
    # Deleting a sales order that already has payments recorded against it
    # (i.e. the customer paid) was failing with a ForeignKeyViolation because
    # payments.sales_order_id had no ON DELETE behavior. Make it cascade so
    # deleting the order deletes its payments too.
    op.drop_constraint("payments_sales_order_id_fkey", "payments", type_="foreignkey")
    op.create_foreign_key(
        "payments_sales_order_id_fkey",
        "payments", "sales_orders",
        ["sales_order_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint("payments_sales_order_id_fkey", "payments", type_="foreignkey")
    op.create_foreign_key(
        "payments_sales_order_id_fkey",
        "payments", "sales_orders",
        ["sales_order_id"], ["id"],
    )
