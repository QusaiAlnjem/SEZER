from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


OrderStatus = Literal["waiting", "shipped"]


def _blank_to_none(v):
    if isinstance(v, str) and not v.strip():
        return None
    return v.strip() if isinstance(v, str) else v


class SupplierIn(BaseModel):
    name: str = Field(min_length=1)          # الاسم
    company_name: Optional[str] = None       # اسم الشركة
    phones: List[str] = Field(default_factory=list)
    email: Optional[str] = None

    _clean = field_validator("company_name", "email", mode="before")(_blank_to_none)

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("phones", mode="before")
    @classmethod
    def _clean_phones(cls, v):
        """Drop the empty extra boxes the 'add another number' button leaves behind."""
        if not isinstance(v, list):
            return v
        seen, out = set(), []
        for p in v:
            p = str(p).strip() if p is not None else ""
            if p and p not in seen:
                seen.add(p)
                out.append(p)
        return out


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    company_name: Optional[str] = None
    phones: List[str] = []
    email: Optional[str] = None
    created_at: datetime
    order_count: int = 0


class OrderProductIn(BaseModel):
    name: Optional[str] = None
    quality: Optional[str] = None     # رقم الطراز
    color: Optional[str] = None
    shade: Optional[str] = None       # رقم الطيف

    _clean = field_validator("name", "quality", "color", "shade", mode="before")(_blank_to_none)

    def is_empty(self) -> bool:
        return not (self.name or self.quality or self.color or self.shade)


class OrderProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: Optional[str] = None
    quality: Optional[str] = None
    color: Optional[str] = None
    shade: Optional[str] = None


class SupplierOrderIn(BaseModel):
    supplier_id: UUID
    order_date: date
    shipping_date: date
    products: List[OrderProductIn] = Field(default_factory=list)


class SupplierOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    order_number: str
    supplier_id: UUID
    supplier_name: Optional[str] = None
    supplier_company: Optional[str] = None
    order_date: date
    shipping_date: date
    status: OrderStatus
    shipped_at: Optional[datetime] = None
    shipment_cost: Optional[Decimal] = None   # تكلفة البضاعة — goods total, USD
    shipping_value: Decimal = Decimal("0")    # تكلفة الشحن
    shipping_is_percent: bool = False
    customs_value: Decimal = Decimal("0")     # تكلفة الجمركة
    customs_is_percent: bool = False
    # resolved from the values above so every caller shows the same numbers
    shipping_amount: Decimal = Decimal("0")
    customs_amount: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")
    created_at: datetime
    products: List[OrderProductOut] = []


class OrderCostsIn(BaseModel):
    """The three costs of a shipment. A null goods total clears it.

    Percentages are of the goods total, so they resolve to nothing while it is
    unset — the UI disables them in that state rather than storing a stray rate.
    """
    shipment_cost: Optional[Decimal] = Field(default=None, ge=0)
    shipping_value: Decimal = Field(default=Decimal("0"), ge=0)
    shipping_is_percent: bool = False
    customs_value: Decimal = Field(default=Decimal("0"), ge=0)
    customs_is_percent: bool = False


class OrderStatusIn(OrderCostsIn):
    """Ship (or un-ship) an order, recording its costs in the same write."""
    status: OrderStatus


class OrderPage(BaseModel):
    """One slice of order history, plus whether another click will fetch more."""
    orders: List[SupplierOrderOut]
    total: int
    has_more: bool
