from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Customer, SalesOrder, SalesOrderItem, Payment, InventoryItem, AccountStatement,
)
from app.schemas import (
    CustomerIn, CustomerOut, CustomerBalance,
    SalesOrderCreate, SalesOrderOut, SalesOrderItemOut, PaymentIn, PaymentOut,
)
from app.schemas.sales import (
    InvoiceOut, InvoiceItem, InvoicePayment, PaymentBatchIn,
    StatementOut, StatementOrder, StatementPayment, StatementProduct,
)
from app.services.auth import get_current_user
from app.services.numbering import next_so_number, next_statement_number
from app.services.inventory import apply_sale_line

router = APIRouter(prefix="/api/creditors", tags=["creditors"], dependencies=[Depends(get_current_user)])


# ---- customers ----

@router.get("/customers", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    return db.query(Customer).order_by(Customer.name).all()


@router.post("/customers", response_model=CustomerOut)
def create_customer(body: CustomerIn, db: Session = Depends(get_db)):
    row = Customer(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/customers/{cid}", response_model=CustomerOut)
def update_customer(cid: UUID, body: CustomerIn, db: Session = Depends(get_db)):
    row = db.get(Customer, cid)
    if not row:
        raise HTTPException(404, "Customer not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/customers/{cid}")
def delete_customer(cid: UUID, db: Session = Depends(get_db)):
    row = db.get(Customer, cid)
    if not row:
        raise HTTPException(404, "Customer not found")

    # Invoices carry the stored totals a customer's balance is built from, so
    # removing the customer under them would strand that history.
    orders = db.query(func.count(SalesOrder.id)).filter(
        SalesOrder.customer_id == cid).scalar() or 0
    if orders:
        raise HTTPException(
            400,
            f"لا يمكن حذف الزبون — لديه {orders} فاتورة. احذف فواتيره أولًا إن أردت إزالته.",
        )

    db.delete(row)
    db.commit()
    return {"ok": True}


# ---- balances (who paid, who owes) ----

@router.get("/balances", response_model=list[CustomerBalance])
def customer_balances(db: Session = Depends(get_db), only_outstanding: bool = False):
    """One row per customer. Everything is USD, so there is nothing to split by."""
    inv_rows = (
        db.query(
            SalesOrder.customer_id,
            func.coalesce(func.sum(SalesOrder.subtotal), 0),
            func.count(SalesOrder.id),
            func.max(SalesOrder.order_date),
        )
        .group_by(SalesOrder.customer_id)
        .all()
    )
    paid_rows = (
        db.query(Payment.customer_id, func.coalesce(func.sum(Payment.amount), 0))
        .group_by(Payment.customer_id)
        .all()
    )
    paid_map: dict = {cid: Decimal(str(amt)) for cid, amt in paid_rows}

    customer_map = {c.id: c for c in db.query(Customer).all()}
    out: list[CustomerBalance] = []
    for cid, invoiced, count, last_date in inv_rows:
        customer = customer_map.get(cid)
        if not customer:
            continue
        invoiced_d = Decimal(str(invoiced))
        paid_d = paid_map.get(cid, Decimal("0"))
        outstanding = invoiced_d - paid_d
        if only_outstanding and outstanding <= 0:
            continue
        out.append(CustomerBalance(
            customer_id=cid,
            customer_name=customer.name,
            phone=customer.phone,
            invoiced=invoiced_d,
            paid=paid_d,
            outstanding=outstanding,
            fully_paid=outstanding <= 0,
            order_count=int(count or 0),
            last_order_date=last_date,
        ))
    out.sort(key=lambda x: (-x.outstanding, x.customer_name))
    return out


# ---- sales orders ----

def _items_total(so: SalesOrder) -> Decimal:
    return sum(
        (Decimal(str(i.line_total or 0)) for i in so.items), Decimal("0")
    ).quantize(Decimal("0.01"))


def _serialize_so(so: SalesOrder) -> SalesOrderOut:
    return SalesOrderOut(
        id=so.id,
        order_number=so.order_number,
        customer_id=so.customer_id,
        customer_name=so.customer.name if so.customer else None,
        order_date=so.order_date,
        items_total=_items_total(so),
        discount=so.discount,
        subtotal=so.subtotal,
        paid_amount=so.paid_amount,
        outstanding=Decimal(str(so.subtotal)) - Decimal(str(so.paid_amount)),
        status=so.status,
        notes=so.notes,
        created_at=so.created_at,
        items=[SalesOrderItemOut(
            id=i.id,
            inventory_item_id=i.inventory_item_id,
            qty=i.qty,
            unit_price=i.unit_price,
            line_total=i.line_total,
            item_name=i.item.name if i.item else None,
            reference=i.item.reference if i.item else None,
            quality=i.item.quality if i.item else None,
            shade=i.item.shade if i.item else None,
            color=i.item.color if i.item else None,
            unit=i.item.unit if i.item else None,
        ) for i in so.items],
        payments=[PaymentOut.model_validate(p) for p in so.payments],
    )


@router.get("/sales-orders", response_model=list[SalesOrderOut])
def list_sos(db: Session = Depends(get_db), customer_id: UUID | None = None, status: str | None = None):
    q = db.query(SalesOrder).options(
        joinedload(SalesOrder.items).joinedload(SalesOrderItem.item),
        joinedload(SalesOrder.payments),
        joinedload(SalesOrder.customer),
    )
    if customer_id:
        q = q.filter(SalesOrder.customer_id == customer_id)
    if status:
        q = q.filter(SalesOrder.status == status)
    q = q.order_by(SalesOrder.created_at.desc())
    return [_serialize_so(s) for s in q.all()]


def _trim(v: Decimal) -> str:
    """1535.000 -> 1535, 4.500 -> 4.5 — Numeric padding reads badly in a message."""
    return f"{Decimal(str(v or 0)).normalize():f}"


def _check_stock(body: SalesOrderCreate, db: Session) -> dict[UUID, InventoryItem]:
    """Refuse the whole order if any line would take an item below zero.

    Quantities are summed per item first, so two lines of the same product
    can't each pass the check and then overdraw the stock together.
    """
    wanted: dict[UUID, Decimal] = {}
    for line in body.items:
        wanted[line.inventory_item_id] = (
            wanted.get(line.inventory_item_id, Decimal("0")) + Decimal(str(line.qty))
        )

    items: dict[UUID, InventoryItem] = {}
    for item_id, qty in wanted.items():
        item = db.get(InventoryItem, item_id)
        if not item:
            raise HTTPException(400, f"Inventory item {item_id} not found")
        on_hand = Decimal(str(item.qty_on_hand or 0))
        if qty > on_hand:
            raise HTTPException(
                400,
                f"الكمية غير كافية من «{item.label}» — "
                f"المطلوب {_trim(qty)} {item.unit} والمتوفر {_trim(on_hand)} {item.unit} فقط.",
            )
        items[item_id] = item
    return items


@router.post("/sales-orders", response_model=SalesOrderOut)
def create_so(body: SalesOrderCreate, db: Session = Depends(get_db)):
    customer = db.get(Customer, body.customer_id)
    if not customer:
        raise HTTPException(400, "Customer not found")
    items = _check_stock(body, db)

    # Everything that can refuse the order is checked before any stock moves,
    # so a rejected request leaves nothing half-applied in the session.
    items_total = sum(
        (Decimal(str(l.qty)) * Decimal(str(l.unit_price)) for l in body.items), Decimal("0")
    ).quantize(Decimal("0.01"))
    discount = Decimal(str(body.discount or 0)).quantize(Decimal("0.01"))
    if discount > items_total:
        raise HTTPException(
            400,
            f"الخصم ({_trim(discount)}$) أكبر من إجمالي الأصناف ({_trim(items_total)}$).",
        )

    so = SalesOrder(
        order_number=next_so_number(db, body.order_date),
        customer_id=body.customer_id,
        order_date=body.order_date,
        status="open",
        notes=body.notes,
        discount=discount,
        subtotal=items_total - discount,
    )
    for line in body.items:
        item = items[line.inventory_item_id]
        so.items.append(SalesOrderItem(
            order=so,
            inventory_item_id=item.id,
            qty=line.qty,
            unit_price=line.unit_price,
        ))
        apply_sale_line(db, item, Decimal(str(line.qty)))
        # Remember what it went for, so the next invoice offers the same price.
        # A zero is a giveaway or a sample, not a price — remembering it would
        # quietly default every later sale of this product to free.
        if Decimal(str(line.unit_price)) > 0:
            item.selling_price = Decimal(str(line.unit_price))
    db.add(so)
    db.commit()
    db.refresh(so)
    return _serialize_so(so)


@router.get("/sales-orders/{sid}", response_model=SalesOrderOut)
def get_so(sid: UUID, db: Session = Depends(get_db)):
    so = db.query(SalesOrder).options(
        joinedload(SalesOrder.items).joinedload(SalesOrderItem.item),
        joinedload(SalesOrder.payments),
        joinedload(SalesOrder.customer),
    ).filter(SalesOrder.id == sid).first()
    if not so:
        raise HTTPException(404, "Sales order not found")
    return _serialize_so(so)


@router.get("/sales-orders/{sid}/invoice", response_model=InvoiceOut)
def invoice(sid: UUID, db: Session = Depends(get_db)):
    """Everything the printed invoice needs, including what the customer
    already owed on other invoices."""
    so = db.query(SalesOrder).options(
        joinedload(SalesOrder.items).joinedload(SalesOrderItem.item),
        joinedload(SalesOrder.payments),
        joinedload(SalesOrder.customer),
    ).filter(SalesOrder.id == sid).first()
    if not so:
        raise HTTPException(404, "Sales order not found")

    # What was still unpaid on invoices issued BEFORE this one.
    # Only earlier invoices count: a later sale must never travel backwards and
    # change what an already-issued invoice says the customer owed at the time.
    others = (
        db.query(
            func.coalesce(func.sum(SalesOrder.subtotal - SalesOrder.paid_amount), 0)
        )
        .filter(
            SalesOrder.customer_id == so.customer_id,
            SalesOrder.id != so.id,
            SalesOrder.created_at < so.created_at,
        )
        .scalar()
    )
    previous_balance = Decimal(str(others or 0))
    outstanding = Decimal(str(so.subtotal)) - Decimal(str(so.paid_amount))

    payments = sorted(so.payments, key=lambda p: p.paid_at)

    return InvoiceOut(
        order_number=so.order_number,
        order_date=so.order_date,
        issued_at=datetime.now(tz=timezone.utc),
        customer_name=so.customer.name if so.customer else "",
        customer_phone=so.customer.phone if so.customer else None,
        customer_city=so.customer.city if so.customer else None,
        items=[InvoiceItem(
            reference=i.item.reference if i.item else None,
            quality=i.item.quality if i.item else None,
            shade=i.item.shade if i.item else None,
            color=i.item.color if i.item else None,
            name=i.item.name if i.item else None,
            unit=i.item.unit if i.item else None,
            qty=i.qty,
            unit_price=i.unit_price,
            line_total=i.line_total,
        ) for i in so.items],
        items_total=_items_total(so),
        discount=so.discount,
        subtotal=so.subtotal,
        payments=[InvoicePayment(paid_at=p.paid_at, amount=p.amount, method=p.method)
                  for p in payments],
        paid_amount=so.paid_amount,
        outstanding=outstanding,
        previous_balance=previous_balance,
        grand_total=outstanding + previous_balance,
    )


# ---- account statements (كشف حساب) ----

def _one_year_back(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:      # 29 Feb landing in a non-leap year
        return d.replace(year=d.year - 1, day=28)


@router.post("/customers/{cid}/statements", response_model=StatementOut)
def create_statement(cid: UUID, db: Session = Depends(get_db)):
    """Issue a كشف حساب covering the year up to today."""
    customer = db.get(Customer, cid)
    if not customer:
        raise HTTPException(404, "Customer not found")

    period_to = date.today()
    row = AccountStatement(
        statement_number=next_statement_number(db, period_to),
        customer_id=cid,
        period_from=_one_year_back(period_to),
        period_to=period_to,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_statement(row, db)


@router.get("/statements/{stid}", response_model=StatementOut)
def get_statement(stid: UUID, db: Session = Depends(get_db)):
    row = db.get(AccountStatement, stid)
    if not row:
        raise HTTPException(404, "Statement not found")
    return _serialize_statement(row, db)


def _serialize_statement(st: AccountStatement, db: Session) -> StatementOut:
    """Recomputed on every view, like an invoice — only the window is stored."""
    customer = st.customer

    orders = (
        db.query(SalesOrder)
        .options(joinedload(SalesOrder.items).joinedload(SalesOrderItem.item))
        .filter(
            SalesOrder.customer_id == st.customer_id,
            SalesOrder.order_date.between(st.period_from, st.period_to),
        )
        .order_by(SalesOrder.order_date, SalesOrder.order_number)
        .all()
    )

    period_invoiced = Decimal("0")
    period_outstanding = Decimal("0")
    out_orders: list[StatementOrder] = []
    for o in orders:
        subtotal = Decimal(str(o.subtotal or 0))
        paid = Decimal(str(o.paid_amount or 0))
        due = subtotal - paid
        period_invoiced += subtotal
        period_outstanding += due
        out_orders.append(StatementOrder(
            order_number=o.order_number,
            order_date=o.order_date,
            subtotal=subtotal,
            paid_amount=paid,
            outstanding=due,
            fully_paid=due <= 0,
        ))

    # Every payment the customer made in the window, whichever invoice it hit.
    payment_rows = (
        db.query(Payment)
        .options(joinedload(Payment.order))
        .filter(
            Payment.customer_id == st.customer_id,
            Payment.paid_at.between(st.period_from, st.period_to),
        )
        .order_by(Payment.paid_at)
        .all()
    )
    period_paid = sum((Decimal(str(p.amount or 0)) for p in payment_rows), Decimal("0"))

    # Most-bought, by quantity. Units can differ between products, but each
    # product is ranked against its own kind, so the comparison holds.
    tally: dict[str, dict] = {}
    for o in orders:
        for line in o.items:
            if not line.item:
                continue
            entry = tally.setdefault(
                str(line.inventory_item_id),
                {"label": line.item.label, "unit": line.item.unit,
                 "qty": Decimal("0"), "spent": Decimal("0")},
            )
            entry["qty"] += Decimal(str(line.qty or 0))
            entry["spent"] += Decimal(str(line.line_total or 0))
    top = sorted(tally.values(), key=lambda e: e["qty"], reverse=True)[:3]

    # The real debt, window or not.
    total_outstanding = Decimal(str(
        db.query(func.coalesce(func.sum(SalesOrder.subtotal - SalesOrder.paid_amount), 0))
        .filter(SalesOrder.customer_id == st.customer_id)
        .scalar() or 0
    ))

    return StatementOut(
        id=st.id,
        statement_number=st.statement_number,
        issued_at=st.created_at,
        period_from=st.period_from,
        period_to=st.period_to,
        customer_name=customer.name if customer else "",
        customer_phone=customer.phone if customer else None,
        customer_city=customer.city if customer else None,
        orders=out_orders,
        period_invoiced=period_invoiced.quantize(Decimal("0.01")),
        period_paid=period_paid.quantize(Decimal("0.01")),
        period_outstanding=period_outstanding.quantize(Decimal("0.01")),
        payments=[StatementPayment(
            paid_at=p.paid_at,
            amount=p.amount,
            method=p.method,
            order_number=p.order.order_number if p.order else None,
        ) for p in payment_rows],
        top_products=[StatementProduct(
            label=e["label"], unit=e["unit"],
            qty=e["qty"], spent=e["spent"].quantize(Decimal("0.01")),
        ) for e in top],
        total_outstanding=total_outstanding.quantize(Decimal("0.01")),
        older_outstanding=(total_outstanding - period_outstanding).quantize(Decimal("0.01")),
    )


@router.delete("/sales-orders/{sid}")
def delete_so(sid: UUID, db: Session = Depends(get_db)):
    so = db.query(SalesOrder).options(joinedload(SalesOrder.items)).filter(SalesOrder.id == sid).first()
    if not so:
        raise HTTPException(404, "Sales order not found")
    # restock the inventory back
    for line in so.items:
        item = db.get(InventoryItem, line.inventory_item_id)
        if item:
            item.qty_on_hand = Decimal(str(item.qty_on_hand)) + Decimal(str(line.qty))
    db.delete(so)
    db.commit()
    return {"ok": True}


# ---- payments ----

def _post_payment(so: SalesOrder, amount: Decimal, body, db: Session) -> Payment:
    """Apply one amount to one invoice, refusing to pay more than it owes.

    Overpaying is blocked rather than allowed to sit as a credit: a customer
    settling several invoices at once should have the money split across them,
    which is what the caller works out before getting here.
    """
    outstanding = Decimal(str(so.subtotal or 0)) - Decimal(str(so.paid_amount or 0))
    if amount > outstanding:
        raise HTTPException(
            400,
            f"المبلغ أكبر من المتبقي على الفاتورة {so.order_number} — "
            f"المتبقي {_trim(outstanding)}$ والمدخل {_trim(amount)}$.",
        )

    payment = Payment(
        sales_order_id=so.id,
        customer_id=so.customer_id,
        paid_at=body.paid_at,
        amount=amount,
        method=body.method,
        notes=body.notes,
    )
    db.add(payment)
    so.paid_amount = Decimal(str(so.paid_amount or 0)) + amount
    so.status = "paid" if so.paid_amount >= Decimal(str(so.subtotal or 0)) else "partial"
    return payment


@router.post("/payments", response_model=PaymentOut)
def add_payment(body: PaymentIn, db: Session = Depends(get_db)):
    so = db.get(SalesOrder, body.sales_order_id)
    if not so:
        raise HTTPException(404, "Sales order not found")
    p = _post_payment(so, Decimal(str(body.amount)), body, db)
    db.commit()
    db.refresh(p)
    return p


@router.post("/payments/batch", response_model=list[PaymentOut])
def add_payment_batch(body: PaymentBatchIn, db: Session = Depends(get_db)):
    """Split one handover across several invoices in a single write."""
    created: list[Payment] = []
    seen: set[UUID] = set()
    for alloc in body.allocations:
        if alloc.sales_order_id in seen:
            raise HTTPException(400, "الفاتورة نفسها مكرّرة في التوزيع")
        seen.add(alloc.sales_order_id)
        so = db.get(SalesOrder, alloc.sales_order_id)
        if not so:
            raise HTTPException(404, f"Sales order {alloc.sales_order_id} not found")
        created.append(_post_payment(so, Decimal(str(alloc.amount)), body, db))

    db.commit()
    for p in created:
        db.refresh(p)
    return created


@router.delete("/payments/{pid}")
def delete_payment(pid: UUID, db: Session = Depends(get_db)):
    p = db.get(Payment, pid)
    if not p:
        raise HTTPException(404, "Payment not found")
    so = db.get(SalesOrder, p.sales_order_id)
    if so:
        so.paid_amount = Decimal(str(so.paid_amount)) - Decimal(str(p.amount))
        so.status = "paid" if so.paid_amount >= so.subtotal else ("partial" if so.paid_amount > 0 else "open")
    db.delete(p)
    db.commit()
    return {"ok": True}
