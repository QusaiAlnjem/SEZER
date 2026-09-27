"""Currency helpers.

Every transaction stores its own fx_to_usd snapshot; this service just picks a
sensible default when the caller doesn't provide one (usually: today's fx_rates
row, else DEFAULT_SYP_PER_USD from env).
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import FxRate


def fx_to_usd_for(db: Session, currency: str, on_day: Optional[date] = None) -> Decimal:
    """Return the multiplier such that `amount * fx_to_usd == amount_in_usd`."""
    if currency == "USD":
        return Decimal("1")
    if currency != "SYP":
        raise ValueError(f"Unsupported currency: {currency}")

    on_day = on_day or date.today()
    row = (
        db.query(FxRate)
        .filter(FxRate.day <= on_day)
        .order_by(FxRate.day.desc())
        .first()
    )
    syp_per_usd = Decimal(str(row.syp_per_usd)) if row else Decimal(str(settings.DEFAULT_SYP_PER_USD))
    if syp_per_usd <= 0:
        syp_per_usd = Decimal(str(settings.DEFAULT_SYP_PER_USD))
    # 1 SYP = (1 / syp_per_usd) USD
    return (Decimal("1") / syp_per_usd).quantize(Decimal("0.00000001"))


def resolve_fx(db: Session, currency: str, provided: Optional[Decimal], on_day: Optional[date] = None) -> Decimal:
    if provided is not None and provided > 0:
        return Decimal(str(provided))
    return fx_to_usd_for(db, currency, on_day)


def current_syp_per_usd(db: Session, on_day: Optional[date] = None) -> Decimal:
    on_day = on_day or date.today()
    row = (
        db.query(FxRate)
        .filter(FxRate.day <= on_day)
        .order_by(FxRate.day.desc())
        .first()
    )
    return Decimal(str(row.syp_per_usd)) if row else Decimal(str(settings.DEFAULT_SYP_PER_USD))
