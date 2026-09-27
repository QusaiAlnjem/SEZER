"""Inventory posting: applying a receipt updates qty_on_hand and recomputes avg cost.

Weighted moving average, in USD, so multi-currency receipts stay comparable.
"""
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import (
    InventoryItem, InventoryReceipt, InventoryReceiptItem, SalesOrder, SalesOrderItem,
)
from app.services.costs import logistics_amount
from app.services.fx import resolve_fx


# Fabric sold by length alerts far later than goods counted in pieces.
LENGTH_UNITS = {"m", "meter", "meters", "metre", "metres", "mtr", "yd", "yard", "yards", "متر"}
DEFAULT_REORDER_LENGTH = Decimal("100")
DEFAULT_REORDER_PIECES = Decimal("10")


def default_reorder_level(unit: Optional[str]) -> Decimal:
    """100 for anything measured by length, 10 for discrete pieces."""
    u = (unit or "").strip().lower()
    return DEFAULT_REORDER_LENGTH if u in LENGTH_UNITS else DEFAULT_REORDER_PIECES


def _clean(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def clean_name(v: Optional[str]) -> Optional[str]:
    """Names take part in identity, so normalise the spacing.

    Without this, "قماش قطن" and "قماش  قطن " are two products that stock and
    cost separately while reading identically on screen.
    """
    if v is None:
        return None
    s = " ".join(str(v).split())
    return s or None


def _match(column, value: Optional[str]):
    """SQL equality that also matches a NULL column against a missing value."""
    return column.is_(None) if value is None else column == value


def find_or_create_item(
    db: Session,
    *,
    inventory_item_id=None,
    reference: Optional[str] = None,
    quality: Optional[str] = None,
    color: Optional[str] = None,
    shade: Optional[str] = None,
    name: Optional[str] = None,
    unit: Optional[str] = None,
) -> InventoryItem:
    """Resolve a receipt line to an item, creating it when it's new.

    Identity is (name, quality, colour, shade). The reference is carried on the
    row but deliberately left out: the same goods arriving under a different
    الرقم التعريفي are still the same product, and should stack rather than
    split into a second row with its own stock and cost.

    A line with no name matches nothing and always becomes a new row. Two
    fabrics can share a طراز, colour and درجة and differ only by name, so
    treating one missing name as equal to another would merge distinct
    products into one pile of stock — silently, and unrecoverably.
    """
    if inventory_item_id:
        item = db.get(InventoryItem, inventory_item_id)
        if item:
            return item

    reference = _clean(reference)
    quality = _clean(quality)
    color = _clean(color)
    shade = _clean(shade)
    name = clean_name(name)

    if quality and name:
        item = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.name == name,
                InventoryItem.quality == quality,
                _match(InventoryItem.shade, shade),
                _match(InventoryItem.color, color),
            )
            .first()
        )
        if item:
            return item

    if not reference or not quality:
        raise ValueError("الرقم التعريفي ورقم الطراز مطلوبان لإنشاء صنف جديد")

    unit = _clean(unit) or "m"
    # A product being added for the first time still carries the price it has
    # sold for before, if this is the same thing under a new row.
    inherited = last_sold_price(db, name=name, quality=quality, color=color, shade=shade)
    item = InventoryItem(
        reference=reference,
        quality=quality,
        color=color,
        shade=shade,
        name=name,
        unit=unit,
        selling_price=inherited if inherited is not None else DEFAULT_SELLING_PRICE,
        reorder_level=default_reorder_level(unit),
    )
    db.add(item)
    db.flush()
    return item


def apply_receipt_line(
    db: Session,
    item: InventoryItem,
    qty: Decimal,               # in the item's stock unit
    unit_cost: Decimal,         # per stock unit
    currency: str,
    fx_to_usd: Optional[Decimal],
) -> Decimal:
    """Update qty_on_hand and the weighted-avg USD cost per unit. Returns fx used."""
    fx = resolve_fx(db, currency, fx_to_usd)
    qty = Decimal(str(qty))
    cost_usd = Decimal(str(unit_cost)) * fx

    current_qty = Decimal(str(item.qty_on_hand or 0))
    current_avg = Decimal(str(item.avg_unit_cost_usd or 0))
    new_qty = current_qty + qty
    if new_qty > 0:
        item.avg_unit_cost_usd = (
            (current_qty * current_avg) + (qty * cost_usd)
        ) / new_qty
    item.qty_on_hand = new_qty
    db.add(item)
    return fx


DEFAULT_SELLING_PRICE = Decimal("1")


def last_sold_price(db: Session, *, name, quality, color, shade) -> Optional[Decimal]:
    """What this product last actually sold for, if it ever has.

    Looser than item identity on purpose: the same fabric in a neighbouring
    درجة sells for the same money, so the name and the طراز must agree and then
    *either* the colour or the درجة. Both sides of whichever field is compared
    have to actually hold a value — a blank matching a blank is not evidence
    that two products are the same thing, so an item recording neither colour
    nor درجة inherits no price.
    """
    name = clean_name(name)
    quality = _clean(quality)
    color = _clean(color)
    shade = _clean(shade)
    if not name or not quality:
        return None

    # only compare the fields this product actually records
    alternatives = []
    if color:
        alternatives.append(InventoryItem.color == color)
    if shade:
        alternatives.append(InventoryItem.shade == shade)
    if not alternatives:
        return None

    return (
        db.query(SalesOrderItem.unit_price)
        .join(SalesOrder, SalesOrder.id == SalesOrderItem.sales_order_id)
        .join(InventoryItem, InventoryItem.id == SalesOrderItem.inventory_item_id)
        .filter(
            InventoryItem.name == name,
            InventoryItem.quality == quality,
            SalesOrderItem.unit_price > 0,   # a giveaway is not a price
            or_(*alternatives),
        )
        .order_by(SalesOrder.order_date.desc(), SalesOrder.created_at.desc())
        .limit(1)
        .scalar()
    )


def find_by_identity(
    db: Session, *, name, quality, color, shade, exclude_ids=()
) -> Optional[InventoryItem]:
    """The item that owns this identity, if one already does.

    Runs without autoflush: callers ask *before* writing the identity they
    intend, so a pending rename must not reach the unique index first.
    """
    name = clean_name(name)
    if not name or not quality:
        return None
    with db.no_autoflush:
        q = db.query(InventoryItem).filter(
            InventoryItem.name == name,
            InventoryItem.quality == quality,
            _match(InventoryItem.shade, _clean(shade)),
            _match(InventoryItem.color, _clean(color)),
        )
        if exclude_ids:
            q = q.filter(InventoryItem.id.notin_(list(exclude_ids)))
        return q.first()


def absorb_item(db: Session, source: InventoryItem, target: InventoryItem) -> None:
    """Fold `source` into `target`, then delete it.

    Naming an imported row can reveal it is a product already on the shelf.
    The stock adds up and `target` keeps its own unit cost — the price already
    established for it stands, rather than being averaged against whatever
    placeholder the import carried in.
    """
    target.qty_on_hand = (
        Decimal(str(target.qty_on_hand or 0)) + Decimal(str(source.qty_on_hand or 0))
    )
    if target.logistics_per_unit is None and source.logistics_per_unit is not None:
        target.logistics_per_unit = source.logistics_per_unit

    # History follows the stock: receipt and invoice lines still pointing at
    # the absorbed row would otherwise reference a deleted item.
    for model in (InventoryReceiptItem, SalesOrderItem):
        db.query(model).filter(model.inventory_item_id == source.id).update(
            {"inventory_item_id": target.id}, synchronize_session=False
        )
    db.delete(source)


def recost_order_receipts(db: Session, order) -> int:
    """Price everything received against a purchase order from what it cost.

    Goods and logistics are spread evenly over the total quantity received, so
    each unit carries `(goods + shipping + customs) / total qty`. That replaces
    the $1 placeholder the receipt form starts from. Mixing units in one
    receipt yields one blended rate — deliberate, since nothing in the data
    says how much of the money belongs to which kind of goods.

    Does nothing while the goods total is unset, which is what leaves goods
    received without a costed order alone.

    Returns the number of receipt lines repriced.
    """
    if order.shipment_cost is None:
        return 0

    lines = [
        line
        for receipt in db.query(InventoryReceipt)
        .filter(InventoryReceipt.supplier_order_id == order.id).all()
        for line in receipt.items
    ]
    total_qty = sum((Decimal(str(l.qty or 0)) for l in lines), Decimal("0"))
    if total_qty <= 0:
        return 0

    goods = Decimal(str(order.shipment_cost))
    logistics = (
        logistics_amount(goods, order.shipping_value, order.shipping_is_percent)
        + logistics_amount(goods, order.customs_value, order.customs_is_percent)
    )
    per_unit_logistics = (logistics / total_qty).quantize(Decimal("0.0001"))
    new_cost = ((goods + logistics) / total_qty).quantize(Decimal("0.0001"))

    touched: set = set()
    for line in lines:
        item = line.item
        if not item:
            continue
        line.unit_cost = new_cost
        item.logistics_per_unit = per_unit_logistics
        db.add(line)
        touched.add(item)

    # Restate each item to the average of everything ever received for it, at
    # corrected prices. Spreading the correction over whatever stock happens to
    # be left instead would load the whole adjustment onto the survivors: with
    # half of a 1000 m delivery already sold, a $2000 bill came out at $3/m and
    # valued the remaining stock at $1500.
    db.flush()
    for item in touched:
        received = db.query(
            func.coalesce(func.sum(InventoryReceiptItem.qty), 0),
            func.coalesce(func.sum(InventoryReceiptItem.qty * InventoryReceiptItem.unit_cost), 0),
        ).filter(InventoryReceiptItem.inventory_item_id == item.id).one()
        total_received, total_spend = Decimal(str(received[0])), Decimal(str(received[1]))
        item.avg_unit_cost_usd = (
            (total_spend / total_received).quantize(Decimal("0.0001"))
            if total_received > 0 else new_cost
        )
        db.add(item)

    return len(lines)


def apply_sale_line(db: Session, item: InventoryItem, qty: Decimal):
    """Decrement qty_on_hand; guard against overselling by allowing negative but flagging."""
    item.qty_on_hand = Decimal(str(item.qty_on_hand or 0)) - Decimal(str(qty))
    db.add(item)
