from uuid import UUID
from datetime import date
from decimal import Decimal
from typing import List, Optional, Literal
from pydantic import BaseModel


Granularity = Literal["day", "month"]


class SeriesPoint(BaseModel):
    """One bar on the profit chart — a single day or a whole month."""
    bucket: str            # "2026-09-12" (day) or "2026-09" (month)
    label: str             # short axis label
    earnings_usd: Decimal
    spending_usd: Decimal
    profit_usd: Decimal


class TodayCard(BaseModel):
    date: date
    inflow_usd: Decimal
    outflow_usd: Decimal
    net_usd: Decimal
    expenses_usd: Decimal


class TotalsCard(BaseModel):
    period_from: date
    period_to: date
    revenue_usd: Decimal
    cogs_usd: Decimal
    opex_usd: Decimal
    purchases_usd: Decimal          # what shipped purchase orders cost in the window
    net_margin_usd: Decimal
    net_margin_pct: Optional[float] = None
    open_so_count: int
    outstanding_ar_usd: Decimal
    low_stock_count: int


class ProductSales(BaseModel):
    inventory_item_id: UUID
    label: str
    unit: str
    qty_sold: Decimal
    revenue_usd: Decimal


class CustomerBrief(BaseModel):
    id: UUID
    name: str
    phone: Optional[str] = None
    city: Optional[str] = None


class DashboardOut(BaseModel):
    today: TodayCard
    totals: TotalsCard
    series: List[SeriesPoint]
    granularity: Granularity
    range_from: date
    range_to: date
    has_earlier: bool          # is there anything before this window to page back to
    top_products: List[ProductSales] = []
    slow_products: List[ProductSales] = []
    customers_this_month: int = 0
    sample_customers: List[CustomerBrief] = []
    fx_syp_per_usd: Decimal
