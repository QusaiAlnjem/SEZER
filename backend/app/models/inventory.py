from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Numeric,
    Integer,
    ForeignKey,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.models._common import pk_uuid, created_at


class InventoryItem(Base):
    """One sellable roll-group: a reference in one specific shade/colour.

    The same `reference` repeats once per shade (a packing list ships
    PROD. NO. 121771 as shades 1..7), so identity is the whole
    (reference, quality, shade, color) tuple. That combination is enforced
    by the `uq_inventory_identity` unique expression index — it lives in
    migration 0005 because it has to COALESCE the two nullable columns.
    """

    __tablename__ = "inventory_items"

    id = pk_uuid()
    reference = Column(String, nullable=False, index=True)   # الرقم التعريفي — PROD. NO.
    quality = Column(String, nullable=False, index=True)     # رقم الطراز — QUALITY / lot
    color = Column(String)                                   # اللون
    shade = Column(String)                                   # رقم الطيف — only when numeric
    name = Column(String)                                    # الاسم
    unit = Column(String, nullable=False, default="m")       # الوحدة
    qty_on_hand = Column(Numeric(14, 3), nullable=False, default=0)
    avg_unit_cost_usd = Column(Numeric(14, 4), nullable=False, default=0)
    # What a unit sells for — nothing to do with what it cost. $1 until the
    # product has actually sold, then the latest sale price.
    selling_price = Column(Numeric(14, 4), nullable=False, default=1)
    # How much of the unit cost is shipping + customs, from the purchase order
    # the goods arrived on. Null means none was ever allocated.
    logistics_per_unit = Column(Numeric(14, 4))
    reorder_level = Column(Numeric(14, 3), nullable=False, default=100)
    created_at = created_at()

    @property
    def label(self) -> str:
        """Human-readable identity, e.g. 'LOT-20 · 121771 · درجة 3'."""
        bits = [self.quality, self.reference]
        if self.shade:
            bits.append(f"درجة {self.shade}")
        if self.color:
            bits.append(self.color)
        if self.name:
            bits.append(self.name)
        return " · ".join(b for b in bits if b)


class InventoryReceipt(Base):
    __tablename__ = "inventory_receipts"

    id = pk_uuid()
    # which supplier order this delivery fulfils; saving the receipt ships it
    supplier_order_id = Column(
        UUID(as_uuid=True), ForeignKey("supplier_orders.id", ondelete="SET NULL")
    )
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes = Column(Text)

    supplier_order = relationship("SupplierOrder")

    items = relationship(
        "InventoryReceiptItem",
        back_populates="receipt",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

class InventoryReceiptItem(Base):
    __tablename__ = "inventory_receipt_items"

    id = pk_uuid()
    receipt_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inventory_receipts.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Stock-in history follows the item: deleting an item that was only ever
    # received takes its receipt lines with it. (Sales lines deliberately do
    # NOT cascade — see delete_item.)
    inventory_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    qty = Column(Numeric(14, 3), nullable=False)          # in the item's stock unit
    unit_cost = Column(Numeric(14, 4), nullable=False)    # cost per stock unit
    currency = Column(String, nullable=False)
    fx_to_usd = Column(Numeric(14, 4), nullable=False)

    receipt = relationship("InventoryReceipt", back_populates="items")
    item = relationship("InventoryItem")

    __table_args__ = (
        CheckConstraint("currency IN ('USD','SYP')", name="rcpt_currency_ck"),
    )




class SpreadsheetImport(Base):
    """A packing list that has been read in.

    The file itself is discarded, but its fingerprint is kept so importing the
    same contents again can be recognised and questioned rather than silently
    doubling every quantity.
    """

    __tablename__ = "spreadsheet_imports"

    id = pk_uuid()
    fingerprint = Column(String(64), nullable=False, index=True)
    filename = Column(String, nullable=False)
    receipt_id = Column(
        UUID(as_uuid=True), ForeignKey("inventory_receipts.id", ondelete="SET NULL")
    )
    rows_imported = Column(Integer, nullable=False, default=0)
    imported_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
