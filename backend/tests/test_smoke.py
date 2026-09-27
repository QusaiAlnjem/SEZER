"""End-to-end smoke pass over every router, against the configured database.

Builds a small world (supplier -> PO -> receipt -> costed -> customer -> sale
-> payment -> statement), asserts the figures at each step, then removes
everything it made. Run with:  python -m pytest tests -q
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import (
    InventoryItem, InventoryReceipt, InventoryReceiptItem, Supplier, SupplierOrder,
    Customer, SalesOrder, AccountStatement, Payment, SpreadsheetImport,
)
from app.core.config import settings

TAG = "SMOKE-TEST"
IMPORT_TAG = "SMOKE-TEST-IMPORT"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        res = c.post("/api/auth/login", data={"username": "owner", "password": settings.OWNER_PIN})
        assert res.status_code == 200, res.text
        c.headers["Authorization"] = f"Bearer {res.json()['access_token']}"
        yield c


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    db = SessionLocal()
    try:
        for st in db.query(AccountStatement).join(Customer).filter(Customer.name == TAG).all():
            db.delete(st)
        db.commit()
        for so in db.query(SalesOrder).join(Customer).filter(Customer.name == TAG).all():
            db.delete(so)
        db.commit()
        item_ids = [i.id for i in db.query(InventoryItem).filter(InventoryItem.quality.like(TAG + "%"))]
        if item_ids:
            db.query(InventoryReceiptItem).filter(
                InventoryReceiptItem.inventory_item_id.in_(item_ids)).delete(synchronize_session=False)
            db.commit()
        for it in db.query(InventoryItem).filter(InventoryItem.quality.like(TAG + "%")).all():
            db.delete(it)
        for o in db.query(SupplierOrder).join(Supplier).filter(Supplier.name == TAG).all():
            db.delete(o)
        db.commit()
        rec_ids = [r.id for r in db.query(InventoryReceipt).filter(
            InventoryReceipt.notes == TAG)]
        if rec_ids:
            # receipt_id is SET NULL on delete, so these must go first
            db.query(SpreadsheetImport).filter(
                SpreadsheetImport.receipt_id.in_(rec_ids)
            ).delete(synchronize_session=False)
            db.commit()
        for r in db.query(InventoryReceipt).filter(InventoryReceipt.notes == TAG).all():
            db.delete(r)
        for s in db.query(Supplier).filter(Supplier.name == TAG).all():
            db.delete(s)
        for c in db.query(Customer).filter(Customer.name == TAG).all():
            db.delete(c)
        db.commit()
    finally:
        db.close()


state: dict = {}


def test_health_and_auth(client):
    assert client.get("/api/health").status_code in (200, 404)
    # an unauthenticated call must be refused
    from fastapi.testclient import TestClient as Bare
    with Bare(app) as anon:
        assert anon.get("/api/storage/items").status_code == 401


def test_supplier_and_purchase_order(client):
    sup = client.post("/api/suppliers", json={"name": TAG, "phones": ["+900000"]})
    assert sup.status_code == 200, sup.text
    state["supplier"] = sup.json()["id"]

    po = client.post("/api/suppliers/orders", json={
        "supplier_id": state["supplier"],
        "order_date": str(date.today()),
        "shipping_date": str(date.today()),
        "products": [{"name": "قماش", "quality": TAG, "color": "أحمر", "shade": "1"}],
    })
    assert po.status_code == 200, po.text
    body = po.json()
    assert body["status"] == "waiting"
    assert len(body["products"]) == 1
    assert body["products"][0]["shade"] == "1"
    state["po"] = body["id"]


def test_receipt_prices_from_order_costs(client):
    rec = client.post("/api/storage/receipts", json={
        "supplier_order_id": state["po"],
        "received_on": str(date.today()),
        "notes": TAG,
        "items": [
            {"reference": "S-1", "quality": TAG, "shade": "1", "name": "قماش أ",
             "qty": 600, "unit": "m"},
            {"reference": "S-2", "quality": TAG, "shade": "2", "name": "قماش ب",
             "qty": 400, "unit": "m"},
        ],
    })
    assert rec.status_code == 200, rec.text
    assert len(rec.json()["items"]) == 2

    # 1000 m for 300 goods + 200 logistics -> 0.50 each, of which 0.20 logistics
    costed = client.patch(f"/api/suppliers/orders/{state['po']}/costs", json={
        "shipment_cost": 300, "shipping_value": 120, "shipping_is_percent": False,
        "customs_value": 80, "customs_is_percent": False,
    })
    assert costed.status_code == 200, costed.text
    assert Decimal(costed.json()["total_cost"]) == Decimal("500.00")

    rows = client.get(f"/api/storage/items?q={TAG}").json()
    assert len(rows) == 2
    for r in rows:
        assert Decimal(r["avg_unit_cost_usd"]) == Decimal("0.5000")
        assert Decimal(r["logistics_per_unit"]) == Decimal("0.2000")
    state["items"] = {r["shade"]: r for r in rows}


def test_spreadsheet_import_keeps_no_file(client):
    """A packing list becomes rows; the file itself is not stored anywhere."""
    rec = client.post("/api/storage/receipts", json={"notes": TAG, "items": []})
    assert rec.status_code == 200, rec.text
    rid = rec.json()["id"]

    csv = (
        "reference,quality,name,qty,unit,unit_cost\n"
        f"IMP-1,{IMPORT_TAG},قماش مستورد,250,m,2\n"
        f"IMP-2,{IMPORT_TAG},قماش آخر,150,m,3\n"
        ",,broken row with no identity,99,m,1\n"
    ).encode("utf-8")

    res = client.post(
        f"/api/storage/receipts/{rid}/import",
        files={"file": ("packing.csv", csv, "text/csv")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["filename"] == "packing.csv"
    assert body["rows_found"] == 2   # the identity-less line never parses
    assert body["imported"] == 2
    assert body["skipped"] == 0

    # the rows landed
    rows = {r["reference"]: r for r in client.get(f"/api/storage/items?q={IMPORT_TAG}").json()}
    assert Decimal(rows["IMP-1"]["qty_on_hand"]) == Decimal("250.000")
    assert Decimal(rows["IMP-2"]["avg_unit_cost_usd"]) == Decimal("3.0000")

    # nothing on the receipt references a stored file any more
    receipt = next(r for r in client.get("/api/storage/receipts").json() if r["id"] == rid)
    assert "documents" not in receipt
    assert len(receipt["items"]) == 2

    # and the old endpoints are gone
    assert client.post(f"/api/storage/receipts/{rid}/documents",
                       files={"file": ("x.csv", csv, "text/csv")}).status_code == 404

    # a format we cannot read is refused rather than silently stored
    bad = client.post(
        f"/api/storage/receipts/{rid}/import",
        files={"file": ("scan.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert bad.status_code == 400


def test_items_paging_and_search(client):
    page = client.get("/api/storage/items?limit=1&offset=0").json()
    assert len(page) == 1
    total = client.get("/api/storage/items/count").json()["total"]
    assert total >= 2
    # search reaches rows beyond the first page — assert on the rows found,
    # not a count, so unrelated fixtures cannot make this brittle
    found = {r["reference"] for r in client.get(f"/api/storage/items?q={TAG}&limit=50").json()}
    assert {"S-1", "S-2"} <= found


def test_stock_guard_and_sale(client):
    cust = client.post("/api/creditors/customers", json={"name": TAG})
    assert cust.status_code == 200, cust.text
    state["customer"] = cust.json()["id"]
    item = state["items"]["1"]

    over = client.post("/api/creditors/sales-orders", json={
        "customer_id": state["customer"], "order_date": str(date.today()),
        "items": [{"inventory_item_id": item["id"], "qty": 99999, "unit_price": 2}],
    })
    assert over.status_code == 400
    assert "الكمية غير كافية" in over.json()["detail"]

    so = client.post("/api/creditors/sales-orders", json={
        "customer_id": state["customer"], "order_date": str(date.today()),
        "items": [{"inventory_item_id": item["id"], "qty": 100, "unit_price": 10}],
        "discount": 57,
    })
    assert so.status_code == 200, so.text
    body = so.json()
    assert Decimal(body["items_total"]) == Decimal("1000.00")
    assert Decimal(body["discount"]) == Decimal("57.00")
    assert Decimal(body["subtotal"]) == Decimal("943.00")
    state["so"] = body["id"]

    inv = client.get(f"/api/creditors/sales-orders/{state['so']}/invoice").json()
    assert Decimal(inv["items_total"]) == Decimal("1000.00")
    assert Decimal(inv["discount"]) == Decimal("57.00")
    assert Decimal(inv["subtotal"]) == Decimal("943.00")


def test_payment_overpay_blocked_and_batch(client):
    over = client.post("/api/creditors/payments", json={
        "sales_order_id": state["so"], "paid_at": str(date.today()),
        "amount": 5000, "method": "cash",
    })
    assert over.status_code == 400
    assert "أكبر من المتبقي" in over.json()["detail"]

    ok = client.post("/api/creditors/payments/batch", json={
        "paid_at": str(date.today()), "method": "cash",
        "allocations": [{"sales_order_id": state["so"], "amount": 943}],
    })
    assert ok.status_code == 200, ok.text
    so = client.get(f"/api/creditors/sales-orders/{state['so']}").json()
    assert so["status"] == "paid"
    assert Decimal(so["outstanding"]) == Decimal("0.00")


def test_selling_price_is_remembered_and_inherited(client):
    """Selling a product teaches the app its price; a matching product inherits it."""
    item = state["items"]["1"]

    # it sold at 10 in the previous test, so the item now carries that
    sold = next(r for r in client.get(f"/api/storage/items?q={TAG}").json()
                if r["id"] == item["id"])
    assert Decimal(sold["selling_price"]) == Decimal("10.0000")
    # and the cost was left exactly as the purchase order worked it out
    assert Decimal(sold["avg_unit_cost_usd"]) == Decimal("0.5000")

    def add(**kw):
        body = {"reference": "X", "quality": TAG, "name": "قماش أ",
                "unit": "m", "qty_on_hand": 5, "unit_cost": 1}
        body.update(kw)
        return client.post("/api/storage/items", json=body)

    # same name + طراز, same shade -> inherits 10
    same_shade = add(reference="NEW-1", shade="1", color="مختلف")
    assert same_shade.status_code == 200, same_shade.text
    assert Decimal(same_shade.json()["selling_price"]) == Decimal("10.0000")

    # same name + طراز, neither colour nor shade in common -> no inheritance
    no_overlap = add(reference="NEW-2", shade="99")
    assert no_overlap.status_code == 200, no_overlap.text
    assert Decimal(no_overlap.json()["selling_price"]) == Decimal("1.0000")

    # a different product entirely -> the $1 default
    other = add(reference="NEW-3", name="قماش مختلف تمامًا", shade="1")
    assert other.status_code == 200, other.text
    assert Decimal(other.json()["selling_price"]) == Decimal("1.0000")

    # nothing recorded for colour or shade -> cannot match, so no inheritance
    blank = add(reference="NEW-4")
    assert blank.status_code == 200, blank.text
    assert Decimal(blank.json()["selling_price"]) == Decimal("1.0000")

    # an explicit price wins over what would have been inherited
    explicit = add(reference="NEW-5", shade="1", color="آخر", selling_price=42)
    assert explicit.status_code == 200, explicit.text
    assert Decimal(explicit.json()["selling_price"]) == Decimal("42.0000")


def test_statement(client):
    st = client.post(f"/api/creditors/customers/{state['customer']}/statements")
    assert st.status_code == 200, st.text
    body = st.json()
    assert body["statement_number"].startswith("ST-")
    assert len(body["orders"]) == 1
    assert Decimal(body["period_invoiced"]) == Decimal("943.00")
    assert Decimal(body["period_paid"]) == Decimal("943.00")
    assert Decimal(body["total_outstanding"]) == Decimal("0.00")
    assert body["top_products"] and Decimal(body["top_products"][0]["qty"]) == Decimal("100.000")
    assert client.get(f"/api/creditors/statements/{body['id']}").status_code == 200


def test_customer_delete_blocked_while_invoiced(client):
    res = client.delete(f"/api/creditors/customers/{state['customer']}")
    assert res.status_code == 400
    assert "لا يمكن حذف الزبون" in res.json()["detail"]


def test_dashboard(client):
    """The page that got least attention — every window and granularity."""
    for days, gran in [(7, "day"), (30, "auto"), (90, "day"), (365, "month")]:
        res = client.get(f"/api/dashboard?days={days}&granularity={gran}")
        assert res.status_code == 200, res.text
        d = res.json()
        t = d["totals"]

        for key in ("revenue_usd", "cogs_usd", "opex_usd", "purchases_usd", "net_margin_usd"):
            assert key in t, f"{key} missing at days={days}"
            Decimal(t[key])          # parses as a number

        # the headline identity the chart is built on
        assert Decimal(t["net_margin_usd"]) == (
            Decimal(t["revenue_usd"]) - Decimal(t["cogs_usd"])
            - Decimal(t["opex_usd"]) - Decimal(t["purchases_usd"])
        ), f"totals don't reconcile at days={days}"

        assert d["granularity"] in ("day", "month")
        assert d["series"], "series should never be empty"
        for p in d["series"]:
            assert Decimal(p["profit_usd"]) == Decimal(p["earnings_usd"]) - Decimal(p["spending_usd"])

        assert len(d["top_products"]) <= 3
        assert len(d["slow_products"]) <= 3
        assert Decimal(d["fx_syp_per_usd"]) >= 0

    # this window contains the sale and the shipped PO we just made
    d = client.get("/api/dashboard?days=30&granularity=day").json()
    assert Decimal(d["totals"]["revenue_usd"]) >= Decimal("943.00")
    assert Decimal(d["totals"]["purchases_usd"]) >= Decimal("500.00")


def test_dashboard_paging_backwards(client):
    old = str(date.today() - timedelta(days=400))
    res = client.get(f"/api/dashboard?days=30&end={old}")
    assert res.status_code == 200
    assert res.json()["range_to"] == old


def test_other_listings(client):
    for path in (
        "/api/suppliers",
        "/api/suppliers/orders?limit=5",
        "/api/creditors/customers",
        "/api/creditors/balances",
        "/api/creditors/sales-orders",
        "/api/storage/receipts",
    ):
        assert client.get(path).status_code == 200, path
