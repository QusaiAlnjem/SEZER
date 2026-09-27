from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Customer, Payment, Expense, SalesOrder, SalesOrderItem, InventoryItem,
    SupplierOrder,
)
from app.schemas.dashboard import (
    DashboardOut, TodayCard, TotalsCard, SeriesPoint, ProductSales, CustomerBrief,
)
from app.services.auth import get_current_user
from app.services.costs import logistics_amount
from app.services.fx import current_syp_per_usd

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])

MAX_DAYS = 366          # a year is the widest window we chart
DAY_BUCKET_LIMIT = 92   # beyond a quarter, days are unreadable — roll up to months

_AR_MONTHS = ["ينا", "فبر", "مار", "أبر", "مايو", "يون",
              "يول", "أغس", "سبت", "أكت", "نوف", "ديس"]


def _zero() -> Decimal:
    return Decimal("0")


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _next_month(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def _q(v: Decimal) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


def _label(item) -> str:
    """Same identity string the rest of the app shows for a product."""
    bits = [item.quality, item.reference]
    if item.shade:
        bits.append(f"درجة {item.shade}")
    if item.color:
        bits.append(item.color)
    if item.name:
        bits.append(item.name)
    return " · ".join(b for b in bits if b)


@router.get("", response_model=DashboardOut)
def dashboard(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=MAX_DAYS),
    end: date | None = Query(None, description="last day of the window; defaults to today"),
    granularity: str | None = Query(None, pattern="^(day|month|auto)$"),
):
    """Earnings / spending / profit over a window, plus the headline cards.

    `end` lets the caller page backwards through history; `days` is capped at a
    year. Granularity follows the span unless it is forced.
    """
    today = date.today()
    range_to = end or today
    span = min(days, MAX_DAYS)
    range_from = range_to - timedelta(days=span - 1)

    mode = granularity or "auto"
    if mode == "auto":
        mode = "day" if span <= DAY_BUCKET_LIMIT else "month"

    # ---- daily aggregates over the window -------------------------------
    earnings_by_day: dict[date, Decimal] = defaultdict(_zero)
    cogs_by_day: dict[date, Decimal] = defaultdict(_zero)
    opex_by_day: dict[date, Decimal] = defaultdict(_zero)
    purchases_by_day: dict[date, Decimal] = defaultdict(_zero)

    for d, total in (
        db.query(SalesOrder.order_date, func.coalesce(func.sum(SalesOrder.subtotal), 0))
        .filter(SalesOrder.order_date.between(range_from, range_to))
        .group_by(SalesOrder.order_date).all()
    ):
        earnings_by_day[d] += Decimal(str(total or 0))

    for d, total in (
        db.query(
            SalesOrder.order_date,
            func.coalesce(func.sum(SalesOrderItem.qty * InventoryItem.avg_unit_cost_usd), 0),
        )
        .join(SalesOrderItem, SalesOrderItem.sales_order_id == SalesOrder.id)
        .join(InventoryItem, InventoryItem.id == SalesOrderItem.inventory_item_id)
        .filter(SalesOrder.order_date.between(range_from, range_to))
        .group_by(SalesOrder.order_date).all()
    ):
        cogs_by_day[d] += Decimal(str(total or 0))

    for d, total in (
        db.query(Expense.spent_at, func.coalesce(func.sum(Expense.amount * Expense.fx_to_usd), 0))
        .filter(Expense.spent_at.between(range_from, range_to))
        .group_by(Expense.spent_at).all()
    ):
        opex_by_day[d] += Decimal(str(total or 0))

    # What purchase orders cost, landing on the day each actually shipped.
    # This is the money paid to suppliers, which overlaps with COGS: goods
    # bought here are also costed again as they sell. Counted anyway, by
    # explicit choice — `purchases_usd` keeps the overlap visible.
    for o in (
        db.query(SupplierOrder)
        .filter(SupplierOrder.shipped_at.isnot(None))
        .filter(func.date(SupplierOrder.shipped_at).between(range_from, range_to))
        .all()
    ):
        goods = Decimal(str(o.shipment_cost or 0))
        purchases_by_day[o.shipped_at.date()] += (
            goods
            + logistics_amount(goods, o.shipping_value, o.shipping_is_percent)
            + logistics_amount(goods, o.customs_value, o.customs_is_percent)
        )

    # ---- bucket into the chart series ----------------------------------
    series: list[SeriesPoint] = []
    if mode == "day":
        for i in range(span):
            d = range_from + timedelta(days=i)
            earn = earnings_by_day.get(d, _zero())
            spend = (
                cogs_by_day.get(d, _zero())
                + opex_by_day.get(d, _zero())
                + purchases_by_day.get(d, _zero())
            )
            series.append(SeriesPoint(
                bucket=d.isoformat(),
                label=f"{d.day}/{d.month}",
                earnings_usd=_q(earn),
                spending_usd=_q(spend),
                profit_usd=_q(earn - spend),
            ))
    else:
        cursor = _month_start(range_from)
        while cursor <= range_to:
            nxt = _next_month(cursor)
            earn = _zero()
            spend = _zero()
            for d, v in earnings_by_day.items():
                if cursor <= d < nxt:
                    earn += v
            for source in (cogs_by_day, opex_by_day, purchases_by_day):
                for d, v in source.items():
                    if cursor <= d < nxt:
                        spend += v
            series.append(SeriesPoint(
                bucket=f"{cursor.year}-{cursor.month:02d}",
                label=f"{_AR_MONTHS[cursor.month - 1]} {str(cursor.year)[2:]}",
                earnings_usd=_q(earn),
                spending_usd=_q(spend),
                profit_usd=_q(earn - spend),
            ))
            cursor = nxt

    # ---- headline totals for the window --------------------------------
    revenue = sum(earnings_by_day.values(), _zero())
    cogs = sum(cogs_by_day.values(), _zero())
    opex = sum(opex_by_day.values(), _zero())
    purchases = sum(purchases_by_day.values(), _zero())
    net_margin = revenue - cogs - opex - purchases
    pct = float((net_margin / revenue) * 100) if revenue > 0 else None

    # ---- today card (always today, independent of the window) ----------
    today_inflow = Decimal(str(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.paid_at == today).scalar() or 0
    ))
    today_expenses = Decimal(str(
        db.query(func.coalesce(func.sum(Expense.amount * Expense.fx_to_usd), 0))
        .filter(Expense.spent_at == today).scalar() or 0
    ))

    # ---- standing figures ----------------------------------------------
    open_so = db.query(func.count(SalesOrder.id)).filter(
        SalesOrder.status.in_(("open", "partial"))).scalar() or 0
    invoiced_usd = Decimal(str(db.query(func.coalesce(func.sum(SalesOrder.subtotal), 0)).scalar() or 0))
    paid_usd = Decimal(str(db.query(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0))
    low_stock = db.query(func.count(InventoryItem.id)).filter(
        InventoryItem.qty_on_hand <= InventoryItem.reorder_level).scalar() or 0

    # ---- best and slowest movers in the window --------------------------
    sales_rows = (
        db.query(
            InventoryItem,
            func.coalesce(func.sum(SalesOrderItem.qty), 0).label("qty"),
            func.coalesce(func.sum(SalesOrderItem.line_total), 0).label("rev"),
        )
        .join(SalesOrderItem, SalesOrderItem.inventory_item_id == InventoryItem.id)
        .join(SalesOrder, SalesOrder.id == SalesOrderItem.sales_order_id)
        .filter(SalesOrder.order_date.between(range_from, range_to))
        .group_by(InventoryItem.id)
        .all()
    )
    ranked = sorted(
        (ProductSales(
            inventory_item_id=item.id,
            label=_label(item),
            unit=item.unit,
            qty_sold=Decimal(str(qty or 0)),
            revenue_usd=_q(rev),
        ) for item, qty, rev in sales_rows),
        key=lambda p: p.qty_sold,
        reverse=True,
    )
    top_products = ranked[:3]
    # slowest movers among things that actually sold; ranking the untouched
    # catalogue would just return an arbitrary three zeroes
    slow_products = list(reversed(ranked[-3:])) if len(ranked) > 3 else []

    # ---- customers ------------------------------------------------------
    month_start = _month_start(today)
    customers_this_month = db.query(
        func.count(func.distinct(SalesOrder.customer_id))
    ).filter(SalesOrder.order_date >= month_start).scalar() or 0

    sample = db.query(Customer).order_by(func.random()).limit(3).all()

    # is there any history before this window worth paging back to?
    earliest = db.query(func.min(SalesOrder.order_date)).scalar()
    earliest_exp = db.query(func.min(Expense.spent_at)).scalar()
    earliest_po = db.query(func.min(func.date(SupplierOrder.shipped_at))).scalar()
    candidates = [d for d in (earliest, earliest_exp, earliest_po) if d]
    has_earlier = bool(candidates) and min(candidates) < range_from

    return DashboardOut(
        today=TodayCard(
            date=today,
            inflow_usd=_q(today_inflow),
            outflow_usd=_q(today_expenses),
            net_usd=_q(today_inflow - today_expenses),
            expenses_usd=_q(today_expenses),
        ),
        totals=TotalsCard(
            period_from=range_from,
            period_to=range_to,
            revenue_usd=_q(revenue),
            cogs_usd=_q(cogs),
            opex_usd=_q(opex),
            purchases_usd=_q(purchases),
            net_margin_usd=_q(net_margin),
            net_margin_pct=pct,
            open_so_count=int(open_so),
            outstanding_ar_usd=_q(invoiced_usd - paid_usd),
            low_stock_count=int(low_stock),
        ),
        series=series,
        granularity=mode,
        range_from=range_from,
        range_to=range_to,
        has_earlier=has_earlier,
        top_products=top_products,
        slow_products=slow_products,
        customers_this_month=int(customers_this_month),
        sample_customers=[
            CustomerBrief(id=c.id, name=c.name, phone=c.phone, city=c.city) for c in sample
        ],
        fx_syp_per_usd=current_syp_per_usd(db),
    )
