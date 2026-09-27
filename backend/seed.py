"""Seed SEZER with realistic demo data. Run: python seed.py"""
from datetime import date, timedelta
from decimal import Decimal

from app.database import SessionLocal
from app.models import (
    User, FxRate, Customer, InventoryItem,
    SalesOrder, SalesOrderItem, Payment, Expense,
)
from app.services.auth import hash_pin, ensure_owner_seeded
from app.services.numbering import next_so_number


def run():
    db = SessionLocal()
    try:
        ensure_owner_seeded(db)

        # FX
        if db.query(FxRate).count() == 0:
            for i in range(30):
                d = date.today() - timedelta(days=i)
                db.add(FxRate(day=d, syp_per_usd=Decimal("15000") + Decimal(i * 5), source="seed"))

        # Customers
        if db.query(Customer).count() == 0:
            db.add(Customer(name="محل الأمل للأقمشة", phone="+963991000001", city="دمشق"))
            db.add(Customer(name="مصنع النور", phone="+963991000002", city="حلب"))
            db.add(Customer(name="متجر الياسمين", phone="+963991000003", city="حمص"))

        # Inventory items — one row per shade, sharing a reference
        if db.query(InventoryItem).count() == 0:
            db.add(InventoryItem(reference="121771", quality="LOT-20", shade="1",
                                 name="قماش قطن 220 غرام", unit="m", reorder_level=Decimal("100")))
            db.add(InventoryItem(reference="121771", quality="LOT-20", shade="2",
                                 name="قماش قطن 220 غرام", unit="m", reorder_level=Decimal("100")))
            db.add(InventoryItem(reference="121776", quality="LOT-25", color="BLACK",
                                 name="بوليستر 150 غرام", unit="m", reorder_level=Decimal("100")))

        db.commit()

        # Prime inventory + a sample sale + a payment
        customer = db.query(Customer).first()
        item_ct = db.query(InventoryItem).filter(
            InventoryItem.reference == "121771", InventoryItem.shade == "1").first()
        item_pl = db.query(InventoryItem).filter(InventoryItem.reference == "121776").first()

        # prime inventory to make the sale/dashboard interesting
        if Decimal(str(item_ct.qty_on_hand)) == 0:
            item_ct.qty_on_hand = Decimal("500")
            item_ct.avg_unit_cost_usd = Decimal("3.50")
        if Decimal(str(item_pl.qty_on_hand)) == 0:
            item_pl.qty_on_hand = Decimal("300")
            item_pl.avg_unit_cost_usd = Decimal("2.10")

        if db.query(SalesOrder).count() == 0:
            so = SalesOrder(
                order_number=next_so_number(db),
                customer_id=customer.id,
                order_date=date.today() - timedelta(days=2),
                status="partial",
                notes="Demo sale",
            )
            so.items.append(SalesOrderItem(inventory_item_id=item_ct.id, qty=Decimal("120"), unit_price=Decimal("5.00")))
            so.items.append(SalesOrderItem(inventory_item_id=item_pl.id, qty=Decimal("80"), unit_price=Decimal("3.20")))
            so.subtotal = Decimal("120")*Decimal("5.00") + Decimal("80")*Decimal("3.20")
            item_ct.qty_on_hand = Decimal(str(item_ct.qty_on_hand)) - Decimal("120")
            item_pl.qty_on_hand = Decimal(str(item_pl.qty_on_hand)) - Decimal("80")
            db.add(so)
            db.flush()

            db.add(Payment(sales_order_id=so.id, customer_id=customer.id, paid_at=date.today() - timedelta(days=1), amount=Decimal("500"), method="cash"))
            so.paid_amount = Decimal("500")

        if db.query(Expense).count() == 0:
            for i in range(5):
                db.add(Expense(category="salary" if i % 2 == 0 else "rent", amount=Decimal("120") + Decimal(i*10), currency="USD", fx_to_usd=Decimal("1"), spent_at=date.today() - timedelta(days=i)))

        db.commit()
        print("Seeded ✓")
    finally:
        db.close()


if __name__ == "__main__":
    run()
