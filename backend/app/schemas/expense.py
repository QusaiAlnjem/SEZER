from uuid import UUID
from datetime import date
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


Currency = Literal["USD", "SYP"]


class ExpenseIn(BaseModel):
    category: str
    amount: Decimal = Field(gt=0)
    currency: Currency
    fx_to_usd: Optional[Decimal] = None
    spent_at: date
    notes: Optional[str] = None


class ExpenseOut(ExpenseIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    fx_to_usd: Decimal
