"""cascade receipt lines when an item is deleted

Deleting an inventory item used to raise a ForeignKeyViolation (surfacing as a
500) because both of its referencing tables were ON DELETE NO ACTION.

Stock-in history may follow the item, so inventory_receipt_items cascades.
sales_order_items deliberately does NOT: sales_orders.subtotal is a stored
column that is never recomputed from its lines, so dropping a sold line would
leave an invoice whose total no longer matches its contents. That case is
refused in the route instead.

Revision ID: 0006_receipt_item_cascade
Revises: 0005_item_identity
Create Date: 2026-09-07 00:00:00
"""
from alembic import op

revision = "0006_receipt_item_cascade"
down_revision = "0005_item_identity"
branch_labels = None
depends_on = None

_FK = "inventory_receipt_items_inventory_item_id_fkey"


def upgrade():
    op.drop_constraint(_FK, "inventory_receipt_items", type_="foreignkey")
    op.create_foreign_key(
        _FK,
        "inventory_receipt_items", "inventory_items",
        ["inventory_item_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint(_FK, "inventory_receipt_items", type_="foreignkey")
    op.create_foreign_key(
        _FK,
        "inventory_receipt_items", "inventory_items",
        ["inventory_item_id"], ["id"],
    )
