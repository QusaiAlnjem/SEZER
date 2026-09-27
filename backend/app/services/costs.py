"""Logistics lines: a flat USD amount, or a percentage of some base.

Shared by sales orders (percent of the products total) and purchase orders
(percent of the goods total) so the two can never drift apart.
"""
from decimal import Decimal


def logistics_amount(base, value, is_percent: bool) -> Decimal:
    value = Decimal(str(value or 0))
    if not is_percent:
        return value.quantize(Decimal("0.01"))
    return (Decimal(str(base or 0)) * value / Decimal("100")).quantize(Decimal("0.01"))
