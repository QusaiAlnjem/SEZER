from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


Currency = Literal["USD", "SYP"]


def _blank_to_none(v):
    """Treat "" / whitespace-only as "not set" so optional text stays NULL."""
    if isinstance(v, str) and not v.strip():
        return None
    return v.strip() if isinstance(v, str) else v


class InventoryItemIn(BaseModel):
    reference: str = Field(min_length=1)   # الرقم التعريفي
    quality: str = Field(min_length=1)     # رقم الطراز
    color: Optional[str] = None            # اللون
    shade: Optional[str] = None            # رقم الطيف (numeric shades only)
    # الاسم — required, because identity keys off it: two fabrics can share a
    # طراز, colour and درجة and be told apart only by name.
    name: str = Field(min_length=1)
    unit: str = "m"                        # الوحدة
    qty_on_hand: Decimal = Field(ge=0)     # الكمية المتوفرة
    unit_cost: Decimal = Field(default=Decimal("1"), ge=0)   # تكلفة الوحدة، بالدولار
    # سعر البيع — what a unit sells for. Omitted means "leave it alone".
    selling_price: Optional[Decimal] = Field(default=None, ge=0)

    _clean_optional = field_validator("color", "shade", mode="before")(_blank_to_none)

    @field_validator("reference", "quality", "unit", mode="before")
    @classmethod
    def _strip_required(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("name", mode="before")
    @classmethod
    def _collapse_name(cls, v):
        return " ".join(str(v).split()) if v is not None else v


class InventoryItemUpdate(InventoryItemIn):
    # Re-apply the edit to every item sharing this reference. Only the shared
    # attributes travel — shade, colour and quantity stay per-item, since those
    # are exactly what makes each row its own product.
    apply_to_reference: bool = False


class InventoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    reference: str
    quality: str
    color: Optional[str] = None
    shade: Optional[str] = None
    name: Optional[str] = None
    unit: str
    qty_on_hand: Decimal
    avg_unit_cost_usd: Decimal
    selling_price: Decimal
    logistics_per_unit: Optional[Decimal] = None   # shipping + customs share
    reorder_level: Decimal
    created_at: datetime


class ItemUpdateOut(BaseModel):
    """The edited item, plus how many rows the save actually touched."""
    item: InventoryItemOut
    updated_count: int = 1
    # rows that turned out to be an existing product and were folded into it
    merged_count: int = 0


class BulkDeleteIn(BaseModel):
    ids: List[UUID] = Field(min_length=1)


class BlockedItem(BaseModel):
    """An item a bulk delete had to skip, and why."""
    id: UUID
    label: str
    sold_lines: int


class BulkDeleteOut(BaseModel):
    deleted: int
    deleted_receipt_lines: int
    blocked: List[BlockedItem] = []


class ReceiptItemIn(BaseModel):
    """A received line. Either points at an existing item, or carries enough
    identity (reference + quality, plus shade/colour) to find or create one."""
    inventory_item_id: Optional[UUID] = None
    reference: Optional[str] = None
    quality: Optional[str] = None
    color: Optional[str] = None
    shade: Optional[str] = None
    # required when typed by hand — it is what decides which product this is.
    # Spreadsheet imports bypass this model and are named afterwards instead.
    name: str = Field(min_length=1)
    qty: Decimal = Field(gt=0)
    unit: str = "m"
    # بالدولار. Null means "price unknown" — the server keeps whatever the item
    # already costs rather than inventing a figure that would skew its average.
    unit_cost: Optional[Decimal] = Field(default=None, ge=0)

    _clean_optional = field_validator(
        "reference", "quality", "color", "shade", mode="before"
    )(_blank_to_none)

    @field_validator("name", mode="before")
    @classmethod
    def _collapse_name(cls, v):
        return " ".join(str(v).split()) if v is not None else v


class ReceiptItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    inventory_item_id: UUID
    item_label: Optional[str] = None
    qty: Decimal
    unit_cost: Decimal
    currency: Currency
    fx_to_usd: Decimal


class ReceiptCreate(BaseModel):
    # the waiting supplier order this delivery fulfils; saving ships it
    supplier_order_id: Optional[UUID] = None
    # when the goods actually arrived; defaults to now if the form omits it
    received_on: Optional[date] = None
    notes: Optional[str] = None
    items: List[ReceiptItemIn] = Field(default_factory=list)  # may be empty if only a doc is uploaded


class ImportResult(BaseModel):
    """What a parsed packing list produced. The file itself is not kept."""
    filename: str
    rows_found: int
    imported: int
    skipped: int          # rows missing the reference/طراز needed to identify them


class ReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_order_id: Optional[UUID] = None
    order_number: Optional[str] = None
    received_at: datetime
    notes: Optional[str] = None
    items: List[ReceiptItemOut] = []
