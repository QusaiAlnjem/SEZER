from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, exists, and_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Supplier, SupplierOrder, SupplierOrderProduct
from app.schemas import (
    SupplierIn, SupplierOut,
    SupplierOrderIn, SupplierOrderOut, OrderProductOut, OrderPage,
    OrderStatusIn, OrderCostsIn,
)
from app.services.auth import get_current_user
from app.services.costs import logistics_amount
from app.services.inventory import recost_order_receipts
from app.services.numbering import next_po_number

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"], dependencies=[Depends(get_current_user)])

DEFAULT_PAGE = 6


# --------------------------------------------------------------------------
# serialisation
# --------------------------------------------------------------------------

def _supplier_out(s: Supplier, order_count: int = 0) -> SupplierOut:
    return SupplierOut(
        id=s.id,
        name=s.name,
        company_name=s.company_name,
        phones=list(s.phones or []),
        email=s.email,
        created_at=s.created_at,
        order_count=order_count,
    )


def _order_out(o: SupplierOrder) -> SupplierOrderOut:
    goods = Decimal(str(o.shipment_cost or 0))
    shipping = logistics_amount(goods, o.shipping_value, o.shipping_is_percent)
    customs = logistics_amount(goods, o.customs_value, o.customs_is_percent)
    return SupplierOrderOut(
        id=o.id,
        order_number=o.order_number,
        supplier_id=o.supplier_id,
        supplier_name=o.supplier.name if o.supplier else None,
        supplier_company=o.supplier.company_name if o.supplier else None,
        order_date=o.order_date,
        shipping_date=o.shipping_date,
        status=o.status,
        shipped_at=o.shipped_at,
        shipment_cost=o.shipment_cost,
        shipping_value=o.shipping_value,
        shipping_is_percent=o.shipping_is_percent,
        customs_value=o.customs_value,
        customs_is_percent=o.customs_is_percent,
        shipping_amount=shipping,
        customs_amount=customs,
        total_cost=(goods + shipping + customs).quantize(Decimal("0.01")),
        created_at=o.created_at,
        products=[OrderProductOut.model_validate(p) for p in o.products],
    )


def _apply_costs(order: SupplierOrder, body: OrderCostsIn) -> None:
    order.shipment_cost = body.shipment_cost
    order.shipping_value = body.shipping_value
    order.shipping_is_percent = body.shipping_is_percent
    order.customs_value = body.customs_value
    order.customs_is_percent = body.customs_is_percent


# --------------------------------------------------------------------------
# suppliers
# --------------------------------------------------------------------------

def _supplier_term(term: str):
    like = f"%{term}%"
    return or_(
        Supplier.name.ilike(like),
        Supplier.company_name.ilike(like),
        Supplier.email.ilike(like),
        # phones is a text[]; flatten it so a partial number still matches
        func.array_to_string(Supplier.phones, " ").ilike(like),
    )


@router.get("", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db), q: str | None = None):
    query = db.query(Supplier)
    if q and q.strip():
        for term in q.split():
            query = query.filter(_supplier_term(term))
    suppliers = query.order_by(Supplier.name).all()

    counts = dict(
        db.query(SupplierOrder.supplier_id, func.count(SupplierOrder.id))
        .group_by(SupplierOrder.supplier_id)
        .all()
    )
    return [_supplier_out(s, int(counts.get(s.id, 0))) for s in suppliers]


@router.post("", response_model=SupplierOut)
def create_supplier(body: SupplierIn, db: Session = Depends(get_db)):
    row = Supplier(
        name=body.name,
        company_name=body.company_name,
        phones=body.phones,
        email=body.email,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _supplier_out(row)


@router.put("/{sid}", response_model=SupplierOut)
def update_supplier(sid: UUID, body: SupplierIn, db: Session = Depends(get_db)):
    row = db.get(Supplier, sid)
    if not row:
        raise HTTPException(404, "Supplier not found")
    row.name = body.name
    row.company_name = body.company_name
    row.phones = body.phones
    row.email = body.email
    db.commit()
    db.refresh(row)
    return _supplier_out(row)


@router.delete("/{sid}")
def delete_supplier(sid: UUID, db: Session = Depends(get_db)):
    row = db.get(Supplier, sid)
    if not row:
        raise HTTPException(404, "Supplier not found")
    orders = db.query(func.count(SupplierOrder.id)).filter(
        SupplierOrder.supplier_id == sid).scalar() or 0
    db.delete(row)   # orders cascade
    db.commit()
    return {"ok": True, "deleted_orders": int(orders)}


# --------------------------------------------------------------------------
# orders
# --------------------------------------------------------------------------

def _order_term(term: str):
    like = f"%{term}%"
    product_hit = exists().where(
        and_(
            SupplierOrderProduct.order_id == SupplierOrder.id,
            or_(
                SupplierOrderProduct.name.ilike(like),
                SupplierOrderProduct.quality.ilike(like),
                SupplierOrderProduct.color.ilike(like),
                SupplierOrderProduct.shade.ilike(like),
            ),
        )
    )
    supplier_hit = exists().where(
        and_(
            Supplier.id == SupplierOrder.supplier_id,
            or_(
                Supplier.name.ilike(like),
                Supplier.company_name.ilike(like),
                func.array_to_string(Supplier.phones, " ").ilike(like),
            ),
        )
    )
    return or_(
        SupplierOrder.order_number.ilike(like),
        SupplierOrder.status.ilike(like),
        product_hit,
        supplier_hit,
    )


def _order_page(query, offset: int, limit: int) -> OrderPage:
    total = query.order_by(None).count()
    rows = (
        query.options(
            joinedload(SupplierOrder.products),
            joinedload(SupplierOrder.supplier),
        )
        .order_by(SupplierOrder.order_date.desc(), SupplierOrder.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return OrderPage(
        orders=[_order_out(o) for o in rows],
        total=int(total),
        has_more=offset + len(rows) < total,
    )


@router.get("/orders", response_model=OrderPage)
def list_orders(
    db: Session = Depends(get_db),
    q: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = DEFAULT_PAGE,
):
    """Newest first, in pages — the UI asks for more only when told to."""
    query = db.query(SupplierOrder)
    if status:
        query = query.filter(SupplierOrder.status == status)
    if q and q.strip():
        for term in q.split():
            query = query.filter(_order_term(term))
    return _order_page(query, offset, max(1, min(limit, 50)))


@router.get("/{sid}/orders", response_model=OrderPage)
def supplier_order_history(
    sid: UUID,
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = DEFAULT_PAGE,
):
    if not db.get(Supplier, sid):
        raise HTTPException(404, "Supplier not found")
    query = db.query(SupplierOrder).filter(SupplierOrder.supplier_id == sid)
    return _order_page(query, offset, max(1, min(limit, 50)))


@router.post("/orders", response_model=SupplierOrderOut)
def create_order(body: SupplierOrderIn, db: Session = Depends(get_db)):
    if not db.get(Supplier, body.supplier_id):
        raise HTTPException(400, "المورد غير موجود")

    order = SupplierOrder(
        order_number=next_po_number(db, body.order_date),
        supplier_id=body.supplier_id,
        order_date=body.order_date,
        shipping_date=body.shipping_date,
        status="waiting",
    )
    # blank product rows are just unused slots in the form
    for p in body.products:
        if p.is_empty():
            continue
        order.products.append(
            SupplierOrderProduct(name=p.name, quality=p.quality, color=p.color, shade=p.shade)
        )
    db.add(order)
    db.commit()
    db.refresh(order)
    return _order_out(order)


@router.patch("/orders/{oid}/status", response_model=SupplierOrderOut)
def set_order_status(oid: UUID, body: OrderStatusIn, db: Session = Depends(get_db)):
    """Ship an order, carrying its costs in the same write.

    The costs are optional — skipping them still ships the order.
    """
    order = db.get(SupplierOrder, oid)
    if not order:
        raise HTTPException(404, "Order not found")

    order.status = body.status
    if body.status == "shipped":
        order.shipped_at = datetime.now(tz=timezone.utc)
        if body.shipment_cost is not None:
            _apply_costs(order, body)
            recost_order_receipts(db, order)
    else:
        # back to waiting: nothing has shipped, so there is no bill either
        order.shipped_at = None
        _apply_costs(order, OrderCostsIn())

    db.commit()
    db.refresh(order)
    return _order_out(order)


@router.patch("/orders/{oid}/costs", response_model=SupplierOrderOut)
def set_order_costs(oid: UUID, body: OrderCostsIn, db: Session = Depends(get_db)):
    """Fill in or correct what a shipment cost. A null goods total clears it.

    Recording a goods total reprices everything received against this order —
    see `recost_order_receipts` — and the total counts as spending on the
    dashboard. Clearing it leaves already-costed items where they are.
    """
    order = db.get(SupplierOrder, oid)
    if not order:
        raise HTTPException(404, "Order not found")
    _apply_costs(order, body)
    recost_order_receipts(db, order)
    db.commit()
    db.refresh(order)
    return _order_out(order)


@router.delete("/orders/{oid}")
def delete_order(oid: UUID, db: Session = Depends(get_db)):
    order = db.get(SupplierOrder, oid)
    if not order:
        raise HTTPException(404, "Order not found")
    db.delete(order)
    db.commit()
    return {"ok": True}
