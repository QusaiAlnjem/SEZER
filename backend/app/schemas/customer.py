from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CustomerIn(BaseModel):
    name: str
    phone: Optional[str] = None
    city: Optional[str] = None
    notes: Optional[str] = None


class CustomerOut(CustomerIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class CustomerBalance(BaseModel):
    """What a customer has been invoiced, paid, and still owes. USD throughout."""
    customer_id: UUID
    customer_name: str
    phone: Optional[str] = None
    invoiced: Decimal
    paid: Decimal
    outstanding: Decimal
    fully_paid: bool
    order_count: int = 0
    last_order_date: Optional[date] = None
