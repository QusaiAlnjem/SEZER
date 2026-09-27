"""Edge cases and invariants — the awkward paths, not the happy one.

Each test builds only what it needs and tears it down, so they can run in any
order. Quality tags all start with EDGE- so cleanup can sweep them.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.database import SessionLocal
from app.models import (
    InventoryItem, InventoryReceipt, InventoryReceiptItem, Supplier, SupplierOrder,
    Customer, SalesOrder, AccountStatement, SpreadsheetImport,
)
from app.services.inventory import last_sold_price
from app.routers.creditors import _one_year_back

PREFIX = "EDGE-"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        res = c.post("/api/auth/login",
                     data={"username": "owner", "password": settings.OWNER_PIN})
        c.headers["Authorization"] = f"Bearer {res.json()['access_token']}"
        yield c


@pytest.fixture(autouse=True)
def cleanup():
    yield
    db = SessionLocal()
    try:
        for st in db.query(AccountStatement).join(Customer).filter(
                Customer.name.like(PREFIX + "%")).all():
            db.delete(st)
        db.commit()
        for so in db.query(SalesOrder).join(Customer).filter(
                Customer.name.like(PREFIX + "%")).all():
            db.delete(so)
        db.commit()
        ids = [i.id for i in db.query(InventoryItem).filter(
            InventoryItem.quality.like(PREFIX + "%"))]
        if ids:
            db.query(InventoryReceiptItem).filter(
                InventoryReceiptItem.inventory_item_id.in_(ids)
            ).delete(synchronize_session=False)
            db.commit()
        for it in db.query(InventoryItem).filter(
                InventoryItem.quality.like(PREFIX + "%")).all():
            db.delete(it)
        db.commit()
        for o in db.query(SupplierOrder).join(Supplier).filter(
                Supplier.name.like(PREFIX + "%")).all():
            db.delete(o)
        db.commit()
        rec_ids = [r.id for r in db.query(InventoryReceipt).filter(
            InventoryReceipt.notes.like(PREFIX + "%"))]
        if rec_ids:
            db.query(SpreadsheetImport).filter(
                SpreadsheetImport.receipt_id.in_(rec_ids)
            ).delete(synchronize_session=False)
            db.commit()
        for r in db.query(InventoryReceipt).filter(
                InventoryReceipt.notes.like(PREFIX + "%")).all():
            db.delete(r)
        for s in db.query(Supplier).filter(Supplier.name.like(PREFIX + "%")).all():
            db.delete(s)
        for c in db.query(Customer).filter(Customer.name.like(PREFIX + "%")).all():
            db.delete(c)
        db.commit()
    finally:
        db.close()


# ---- helpers ----------------------------------------------------------------

def make_supplier(client, tag):
    return client.post("/api/suppliers", json={"name": PREFIX + tag}).json()["id"]


def make_po(client, sid):
    return client.post("/api/suppliers/orders", json={
        "supplier_id": sid,
        "order_date": str(date.today()),
        "shipping_date": str(date.today()),
        "products": [],
    }).json()["id"]


def make_receipt(client, tag, lines, po=None):
    body = {"notes": PREFIX + tag, "items": lines}
    if po:
        body["supplier_order_id"] = po
    res = client.post("/api/storage/receipts", json=body)
    assert res.status_code == 200, res.text
    return res.json()["id"]


def line(tag, shade, qty, name="قماش", **kw):
    d = {"reference": f"R-{shade}", "quality": PREFIX + tag, "shade": shade,
         "name": name, "qty": qty, "unit": "m"}
    d.update(kw)
    return d


def items_for(client, tag):
    rows = client.get(f"/api/storage/items?q={PREFIX + tag}&limit=100").json()
    return {r["shade"]: r for r in rows}


def make_customer(client, tag):
    return client.post("/api/creditors/customers", json={"name": PREFIX + tag}).json()["id"]


# ---- purchase-order costing -------------------------------------------------

def test_cost_spreads_across_every_receipt_on_one_order(client):
    """Two deliveries against one PO share its cost by total quantity."""
    tag = "COST1"
    sid = make_supplier(client, tag)
    po = make_po(client, sid)
    make_receipt(client, tag, [line(tag, "1", 600)], po=po)
    make_receipt(client, tag, [line(tag, "2", 400)], po=po)

    res = client.patch(f"/api/suppliers/orders/{po}/costs", json={"shipment_cost": 500})
    assert res.status_code == 200, res.text

    rows = items_for(client, tag)
    # 500 over 1000 m total, not 500 over each receipt
    assert Decimal(rows["1"]["avg_unit_cost_usd"]) == Decimal("0.5000")
    assert Decimal(rows["2"]["avg_unit_cost_usd"]) == Decimal("0.5000")


def test_recosting_twice_with_the_same_figures_does_not_drift(client):
    tag = "COST2"
    sid = make_supplier(client, tag)
    po = make_po(client, sid)
    make_receipt(client, tag, [line(tag, "1", 1000)], po=po)

    payload = {"shipment_cost": 300, "shipping_value": 100, "customs_value": 100}
    first = client.patch(f"/api/suppliers/orders/{po}/costs", json=payload)
    assert first.status_code == 200
    after_one = items_for(client, tag)["1"]["avg_unit_cost_usd"]

    for _ in range(3):
        client.patch(f"/api/suppliers/orders/{po}/costs", json=payload)
    after_many = items_for(client, tag)["1"]["avg_unit_cost_usd"]

    assert Decimal(after_one) == Decimal("0.5000")
    assert Decimal(after_many) == Decimal(after_one), "repeated recosting drifted"


def test_zero_goods_cost_is_honoured_not_ignored(client):
    """A deliberate 0 means free goods, and must not be read as 'unset'."""
    tag = "COST3"
    sid = make_supplier(client, tag)
    po = make_po(client, sid)
    make_receipt(client, tag, [line(tag, "1", 100)], po=po)
    client.patch(f"/api/suppliers/orders/{po}/costs", json={"shipment_cost": 0})
    assert Decimal(items_for(client, tag)["1"]["avg_unit_cost_usd"]) == Decimal("0.0000")


def test_unpriced_receipt_of_known_goods_leaves_cost_alone(client):
    tag = "COST4"
    sid = make_supplier(client, tag)
    po = make_po(client, sid)
    make_receipt(client, tag, [line(tag, "1", 1000)], po=po)
    client.patch(f"/api/suppliers/orders/{po}/costs", json={"shipment_cost": 2000})
    assert Decimal(items_for(client, tag)["1"]["avg_unit_cost_usd"]) == Decimal("2.0000")

    # more of the same goods, no PO, no stated price
    make_receipt(client, tag, [line(tag, "1", 500)])
    row = items_for(client, tag)["1"]
    assert Decimal(row["qty_on_hand"]) == Decimal("1500.000")
    assert Decimal(row["avg_unit_cost_usd"]) == Decimal("2.0000"), "placeholder leaked in"


def test_recosting_after_a_sale_does_not_overstate_cost(client):
    """The correction belongs to everything received, not just what's left.

    Regression: spreading it over surviving stock turned a $2000 bill for
    1000 m into $3/m once half had sold, valuing 500 m at $1500.
    """
    tag = "COST5"
    sid = make_supplier(client, tag)
    po = make_po(client, sid)
    make_receipt(client, tag, [line(tag, "1", 1000)], po=po)
    item = items_for(client, tag)["1"]
    cust = make_customer(client, tag)

    sold = client.post("/api/creditors/sales-orders", json={
        "customer_id": cust, "order_date": str(date.today()),
        "items": [{"inventory_item_id": item["id"], "qty": 500, "unit_price": 9}],
    })
    assert sold.status_code == 200, sold.text

    client.patch(f"/api/suppliers/orders/{po}/costs", json={"shipment_cost": 2000})

    row = items_for(client, tag)["1"]
    assert Decimal(row["avg_unit_cost_usd"]) == Decimal("2.0000")
    # 500 m left of goods that cost $2/m
    assert (Decimal(row["qty_on_hand"]) * Decimal(row["avg_unit_cost_usd"])
            == Decimal("1000.0000"))


def test_a_giveaway_is_not_remembered_as_the_price(client):
    """Selling one at zero must not default every later invoice to free."""
    tag = "SELL3"
    make_receipt(client, tag, [line(tag, "1", 100)])
    item = items_for(client, tag)["1"]
    cust = make_customer(client, tag)

    paid = client.post("/api/creditors/sales-orders", json={
        "customer_id": cust, "order_date": str(date.today() - timedelta(days=3)),
        "items": [{"inventory_item_id": item["id"], "qty": 1, "unit_price": 12}],
    })
    assert paid.status_code == 200, paid.text
    assert Decimal(items_for(client, tag)["1"]["selling_price"]) == Decimal("12.0000")

    free = client.post("/api/creditors/sales-orders", json={
        "customer_id": cust, "order_date": str(date.today()),
        "items": [{"inventory_item_id": item["id"], "qty": 1, "unit_price": 0}],
    })
    assert free.status_code == 200, free.text
    assert Decimal(items_for(client, tag)["1"]["selling_price"]) == Decimal("12.0000")

    db = SessionLocal()
    try:
        found = last_sold_price(db, name="قماش", quality=PREFIX + tag,
                                color=None, shade="1")
        assert found is not None and Decimal(found) == Decimal("12.0000")
    finally:
        db.close()


# ---- stock -----------------------------------------------------------------

def test_deleting_an_invoice_restores_stock_exactly(client):
    tag = "STOCK1"
    make_receipt(client, tag, [line(tag, "1", 100)])
    item = items_for(client, tag)["1"]
    cust = make_customer(client, tag)

    so = client.post("/api/creditors/sales-orders", json={
        "customer_id": cust, "order_date": str(date.today()),
        "items": [{"inventory_item_id": item["id"], "qty": "37.5", "unit_price": 4}],
    })
    assert so.status_code == 200, so.text
    assert Decimal(items_for(client, tag)["1"]["qty_on_hand"]) == Decimal("62.500")

    client.delete(f"/api/creditors/sales-orders/{so.json()['id']}")
    assert Decimal(items_for(client, tag)["1"]["qty_on_hand"]) == Decimal("100.000")


def test_same_item_on_two_lines_cannot_overdraw(client):
    tag = "STOCK2"
    make_receipt(client, tag, [line(tag, "1", 100)])
    item = items_for(client, tag)["1"]
    cust = make_customer(client, tag)

    res = client.post("/api/creditors/sales-orders", json={
        "customer_id": cust, "order_date": str(date.today()),
        "items": [
            {"inventory_item_id": item["id"], "qty": 60, "unit_price": 1},
            {"inventory_item_id": item["id"], "qty": 60, "unit_price": 1},
        ],
    })
    assert res.status_code == 400
    # and the refusal left the stock untouched
    assert Decimal(items_for(client, tag)["1"]["qty_on_hand"]) == Decimal("100.000")


def test_a_refused_invoice_moves_no_stock(client):
    """The discount check runs before stock does, so a bad discount is inert."""
    tag = "STOCK3"
    make_receipt(client, tag, [line(tag, "1", 100)])
    item = items_for(client, tag)["1"]
    cust = make_customer(client, tag)

    res = client.post("/api/creditors/sales-orders", json={
        "customer_id": cust, "order_date": str(date.today()),
        "items": [{"inventory_item_id": item["id"], "qty": 10, "unit_price": 5}],
        "discount": 9999,
    })
    assert res.status_code == 400
    assert Decimal(items_for(client, tag)["1"]["qty_on_hand"]) == Decimal("100.000")


# ---- discount --------------------------------------------------------------

def test_discount_equal_to_the_total_bills_nothing(client):
    tag = "DISC1"
    make_receipt(client, tag, [line(tag, "1", 100)])
    item = items_for(client, tag)["1"]
    cust = make_customer(client, tag)

    so = client.post("/api/creditors/sales-orders", json={
        "customer_id": cust, "order_date": str(date.today()),
        "items": [{"inventory_item_id": item["id"], "qty": 10, "unit_price": 5}],
        "discount": 50,
    })
    assert so.status_code == 200, so.text
    body = so.json()
    assert Decimal(body["items_total"]) == Decimal("50.00")
    assert Decimal(body["subtotal"]) == Decimal("0.00")
    assert Decimal(body["outstanding"]) == Decimal("0.00")

    # nothing is owed, so the customer reads as settled
    bal = next(b for b in client.get("/api/creditors/balances").json()
               if b["customer_id"] == cust)
    assert bal["fully_paid"] is True

    # and a payment on it is refused rather than creating a credit
    pay = client.post("/api/creditors/payments", json={
        "sales_order_id": body["id"], "paid_at": str(date.today()),
        "amount": 1, "method": "cash",
    })
    assert pay.status_code == 400


# ---- selling price ---------------------------------------------------------

def test_selling_price_follows_the_latest_sale_not_the_highest(client):
    tag = "SELL1"
    make_receipt(client, tag, [line(tag, "1", 100)])
    item = items_for(client, tag)["1"]
    cust = make_customer(client, tag)

    for price, day in [(20, 5), (8, 1)]:          # 20 first, then 8 more recently
        res = client.post("/api/creditors/sales-orders", json={
            "customer_id": cust,
            "order_date": str(date.today() - timedelta(days=day)),
            "items": [{"inventory_item_id": item["id"], "qty": 1, "unit_price": price}],
        })
        assert res.status_code == 200, res.text

    assert Decimal(items_for(client, tag)["1"]["selling_price"]) == Decimal("8.0000")

    db = SessionLocal()
    try:
        found = last_sold_price(db, name="قماش", quality=PREFIX + tag,
                                color=None, shade="1")
        assert found is not None and Decimal(found) == Decimal("8.0000")
    finally:
        db.close()


def test_selling_price_needs_colour_or_shade_in_common(client):
    tag = "SELL2"
    make_receipt(client, tag, [line(tag, "7", 10)])
    item = items_for(client, tag)["7"]
    cust = make_customer(client, tag)
    client.post("/api/creditors/sales-orders", json={
        "customer_id": cust, "order_date": str(date.today()),
        "items": [{"inventory_item_id": item["id"], "qty": 1, "unit_price": 33}],
    })

    db = SessionLocal()
    try:
        q = PREFIX + tag
        # shade agrees -> inherits
        assert Decimal(last_sold_price(db, name="قماش", quality=q,
                                       color="أحمر", shade="7")) == Decimal("33.0000")
        # nothing in common -> no price
        assert last_sold_price(db, name="قماش", quality=q, color="أحمر", shade="8") is None
        # neither field recorded -> cannot match
        assert last_sold_price(db, name="قماش", quality=q, color=None, shade=None) is None
        # different name -> different product
        assert last_sold_price(db, name="آخر", quality=q, color=None, shade="7") is None
    finally:
        db.close()


# ---- statements ------------------------------------------------------------

def test_statement_window_includes_both_boundaries(client):
    tag = "STMT1"
    make_receipt(client, tag, [line(tag, "1", 1000)])
    item = items_for(client, tag)["1"]
    cust = make_customer(client, tag)

    today = date.today()
    inside_new = today
    inside_old = _one_year_back(today)
    outside = inside_old - timedelta(days=1)

    for d in (inside_new, inside_old, outside):
        res = client.post("/api/creditors/sales-orders", json={
            "customer_id": cust, "order_date": str(d),
            "items": [{"inventory_item_id": item["id"], "qty": 1, "unit_price": 10}],
        })
        assert res.status_code == 200, res.text

    st = client.post(f"/api/creditors/customers/{cust}/statements").json()
    dates = {o["order_date"] for o in st["orders"]}
    assert str(inside_new) in dates
    assert str(inside_old) in dates, "the first day of the window was excluded"
    assert str(outside) not in dates

    # the older invoice still counts toward what is really owed
    assert Decimal(st["period_outstanding"]) == Decimal("20.00")
    assert Decimal(st["total_outstanding"]) == Decimal("30.00")
    assert Decimal(st["older_outstanding"]) == Decimal("10.00")


def test_one_year_back_survives_a_leap_day():
    assert _one_year_back(date(2025, 3, 1)) == date(2024, 3, 1)
    # 29 Feb has no counterpart in a non-leap year
    assert _one_year_back(date(2024, 2, 29)) == date(2023, 2, 28)


# ---- spreadsheet import ----------------------------------------------------

CSV = (
    "reference,quality,shade,qty,unit\n"
    "121771,{q},1,1000,m\n"
    "121771,{q},2,500,m\n"
)


def test_importing_the_same_list_twice_into_one_receipt_is_refused(client):
    """Two guards, in order: the fingerprint, then the quantities on the receipt."""
    tag = "IMP1"
    rid = make_receipt(client, tag, [])
    csv = CSV.format(q=PREFIX + tag).encode()

    first = client.post(f"/api/storage/receipts/{rid}/import",
                        files={"file": ("pl.csv", csv, "text/csv")})
    assert first.status_code == 200, first.text
    assert first.json()["imported"] == 2

    # recognised by contents — overridable, because a repeat shipment is real
    second = client.post(f"/api/storage/receipts/{rid}/import",
                         files={"file": ("pl.csv", csv, "text/csv")})
    assert second.status_code == 409, "a second import into the same receipt double-counts"

    # even forced, doubling *within one receipt* is still refused: these exact
    # quantities are already sitting on it
    forced = client.post(f"/api/storage/receipts/{rid}/import?force=true",
                         files={"file": ("pl.csv", csv, "text/csv")})
    assert forced.status_code == 400, "forcing bypassed the per-receipt guard too"

    rows = items_for(client, tag)
    assert Decimal(rows["1"]["qty_on_hand"]) == Decimal("1000.000")


def test_naming_imported_rows_merges_them_and_keeps_the_price(client):
    """Unnamed rows do not stack; naming them is what folds them together."""
    tag = "IMP2"
    csv = CSV.format(q=PREFIX + tag).encode()
    for n in range(2):
        rid = make_receipt(client, tag, [])
        # the second is a deliberate repeat, so force past the fingerprint
        res = client.post(
            f"/api/storage/receipts/{rid}/import" + ("?force=true" if n else ""),
            files={"file": ("pl.csv", csv, "text/csv")})
        assert res.status_code == 200, res.text

    rows = client.get(f"/api/storage/items?q={PREFIX + tag}&limit=100").json()
    assert len(rows) == 4, "unnamed rows are expected to stay separate"

    # naming every row folds each shade into one, quantities summed
    for r in rows:
        upd = client.put(f"/api/storage/items/{r['id']}", json={
            "reference": r["reference"], "quality": r["quality"],
            "color": r["color"], "shade": r["shade"], "name": "هندي شتوي",
            "unit": r["unit"], "qty_on_hand": float(r["qty_on_hand"]),
            "unit_cost": float(r["avg_unit_cost_usd"]),
        })
        assert upd.status_code == 200, upd.text

    merged = items_for(client, tag)
    assert len(merged) == 2
    assert Decimal(merged["1"]["qty_on_hand"]) == Decimal("2000.000")
    assert Decimal(merged["2"]["qty_on_hand"]) == Decimal("1000.000")


def test_the_same_list_is_recognised_across_different_receipts(client):
    """The per-receipt guard can't see this; the fingerprint can."""
    tag = "IMP4"
    csv = CSV.format(q=PREFIX + tag).encode()

    first = client.post(f"/api/storage/receipts/{make_receipt(client, tag, [])}/import",
                        files={"file": ("pl.csv", csv, "text/csv")})
    assert first.status_code == 200, first.text

    # a different receipt entirely — nothing on it to compare quantities against
    rid2 = make_receipt(client, tag, [])
    again = client.post(f"/api/storage/receipts/{rid2}/import",
                        files={"file": ("pl.csv", csv, "text/csv")})
    assert again.status_code == 409, "a repeat across receipts went unnoticed"
    assert "مستوردة من قبل" in again.json()["detail"]

    # nothing was added by the refusal
    assert Decimal(items_for(client, tag)["1"]["qty_on_hand"]) == Decimal("1000.000")

    # a genuine repeat shipment can still be imported deliberately
    forced = client.post(f"/api/storage/receipts/{rid2}/import?force=true",
                         files={"file": ("pl.csv", csv, "text/csv")})
    assert forced.status_code == 200, forced.text
    rows = client.get(f"/api/storage/items?q={PREFIX + tag}&limit=100").json()
    assert len(rows) == 4, "forcing should add the rows, not swallow them"


def test_a_resaved_file_with_the_same_contents_is_still_recognised(client):
    """Fingerprinting the parsed rows, not the bytes, survives a re-export."""
    tag = "IMP5"
    q = PREFIX + tag
    original = f"reference,quality,shade,qty,unit\n121771,{q},1,1000,m\n".encode()
    # same contents, different bytes: reordered columns and extra whitespace
    resaved = f"quality,shade,reference,unit,qty\n{q}, 1 ,121771,m,1000\n".encode()

    a = client.post(f"/api/storage/receipts/{make_receipt(client, tag, [])}/import",
                    files={"file": ("pl.csv", original, "text/csv")})
    assert a.status_code == 200, a.text

    b = client.post(f"/api/storage/receipts/{make_receipt(client, tag, [])}/import",
                    files={"file": ("pl-v2.csv", resaved, "text/csv")})
    assert b.status_code == 409, "a re-saved copy of the same list slipped through"


def test_a_genuinely_different_list_is_not_blocked(client):
    tag = "IMP6"
    q = PREFIX + tag
    first = f"reference,quality,shade,qty,unit\n121771,{q},1,1000,m\n".encode()
    other = f"reference,quality,shade,qty,unit\n121771,{q},1,1200,m\n".encode()

    a = client.post(f"/api/storage/receipts/{make_receipt(client, tag, [])}/import",
                    files={"file": ("pl.csv", first, "text/csv")})
    assert a.status_code == 200, a.text
    # a different quantity is a different shipment
    b = client.post(f"/api/storage/receipts/{make_receipt(client, tag, [])}/import",
                    files={"file": ("pl.csv", other, "text/csv")})
    assert b.status_code == 200, b.text


def test_import_rejects_a_format_it_cannot_read(client):
    tag = "IMP3"
    rid = make_receipt(client, tag, [])
    res = client.post(f"/api/storage/receipts/{rid}/import",
                      files={"file": ("scan.pdf", b"%PDF-1.4", "application/pdf")})
    assert res.status_code == 400


# ---- numbering -------------------------------------------------------------

def test_numbers_restart_each_month(client):
    tag = "NUM1"
    sid = make_supplier(client, tag)
    this_month = date.today().replace(day=1)
    last_month = (this_month - timedelta(days=1)).replace(day=1)

    a = client.post("/api/suppliers/orders", json={
        "supplier_id": sid, "order_date": str(last_month),
        "shipping_date": str(last_month), "products": [],
    }).json()["order_number"]
    b = client.post("/api/suppliers/orders", json={
        "supplier_id": sid, "order_date": str(this_month),
        "shipping_date": str(this_month), "products": [],
    }).json()["order_number"]

    assert a.startswith(f"PO-{last_month:%Y%m}-")
    assert b.startswith(f"PO-{this_month:%Y%m}-")
    assert a.rsplit("-", 1)[1] == "0001" or b.rsplit("-", 1)[1] == "0001"
