from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class FxIn(BaseModel):
    day: date
    syp_per_usd: Decimal = Field(gt=0)
    source: str = "manual"


class FxOut(FxIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
