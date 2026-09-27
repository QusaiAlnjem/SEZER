import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from sqlalchemy import func, case, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    InventoryItem, InventoryReceipt, InventoryReceiptItem, SpreadsheetImport,
    SalesOrderItem, SupplierOrder,
)
from app.schemas import (
    InventoryItemIn, InventoryItemUpdate, InventoryItemOut, ItemUpdateOut,
    BulkDeleteIn, BulkDeleteOut,
    ReceiptCreate, ReceiptOut, ReceiptItemOut, ImportResult,
)
from app.schemas.inventory import BlockedItem
from app.services.auth import get_current_user
from app.services.inventory import (
    find_or_create_item, apply_receipt_line, default_reorder_level, clean_name,
    find_by_identity, absorb_item, last_sold_price, DEFAULT_SELLING_PRICE,
)
from app.services.excel import parse_excel, parse_csv, DEFAULT_UNIT_COST

router = APIRouter(prefix="/api/storage", tags=["storage"], dependencies=[Depends(get_current_user)])



# ---- items ----

def _as_number(term: str):
    try:
        return Decimal(term.replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _term_matches(term: str):
    """One search term against anything on the row.

    Text is matched as a substring, but shade and the numeric columns are
    matched *exactly* — otherwise "3" would hit quantity 1535.900 and "2"
    would hit the name "قماش قطن 220", which makes multi-word search useless.
    """
    like = f"%{term}%"
    conds = [
        InventoryItem.reference.ilike(like),
        InventoryItem.quality.ilike(like),
        InventoryItem.color.ilike(like),
        InventoryItem.name.ilike(like),
        InventoryItem.unit.ilike(like),
        # so searching the badge text "درجة 3" works the way it reads
        case(
            (InventoryItem.shade.isnot(None), func.concat("درجة ", InventoryItem.shade)),
            else_=None,
        ).ilike(like),
        func.lower(func.coalesce(InventoryItem.shade, "")) == term.lower(),
    ]
    number = _as_number(term)
    if number is not None:
        conds.append(InventoryItem.qty_on_hand == number)
        conds.append(InventoryItem.avg_unit_cost_usd == number)
    return or_(*conds)


@router.get("/items", response_model=list[InventoryItemOut])
def list_items(
    db: Session = Depends(get_db),
    q: str | None = None,
    low_stock: bool = False,
    offset: int = 0,
    limit: int | None = None,
):
    """Items, newest-relevant first.

    `limit` pages the list for the warehouse screen; the search still runs
    across the whole table, so a term finds a row that is far past the first
    page. Callers that need the full set (the pickers) simply omit `limit`.
    """
    query = db.query(InventoryItem)
    if q and q.strip():
        # Every term must match something, so "121771 3" narrows to shade 3
        # rather than returning everything that matches either half.
        for term in q.split():
            query = query.filter(_term_matches(term))
    if low_stock:
        query = query.filter(InventoryItem.qty_on_hand <= InventoryItem.reorder_level)

    query = query.order_by(
        InventoryItem.quality, InventoryItem.reference, InventoryItem.shade, InventoryItem.color
    )
    if limit is not None:
        query = query.offset(max(0, offset)).limit(max(1, min(limit, 200)))
    return query.all()


@router.get("/items/count")
def count_items(db: Session = Depends(get_db), q: str | None = None, low_stock: bool = False):
    """How many rows the same filters match — lets the UI show a real total."""
    query = db.query(func.count(InventoryItem.id))
    if q and q.strip():
        for term in q.split():
            query = query.filter(_term_matches(term))
    if low_stock:
        query = query.filter(InventoryItem.qty_on_hand <= InventoryItem.reorder_level)
    return {"total": int(query.scalar() or 0)}


def _apply_item_fields(row: InventoryItem, body: InventoryItemIn, db: Session) -> None:
    row.reference = body.reference
    row.quality = body.quality
    row.color = body.color
    row.shade = body.shade
    row.name = clean_name(body.name)   # the name is part of identity
    row.unit = body.unit or "m"
    row.qty_on_hand = body.qty_on_hand
    row.avg_unit_cost_usd = Decimal(str(body.unit_cost))   # costs are entered in USD
    if body.selling_price is not None:
        row.selling_price = Decimal(str(body.selling_price))


@router.post("/items", response_model=InventoryItemOut)
def create_item(body: InventoryItemIn, db: Session = Depends(get_db)):
    row = InventoryItem()
    _apply_item_fields(row, body, db)
    # the alert threshold is not on the form — it follows the unit
    row.reorder_level = default_reorder_level(row.unit)
    if body.selling_price is None:
        # no price given: carry over what this product last sold for
        inherited = last_sold_price(
            db, name=row.name, quality=row.quality, color=row.color, shade=row.shade
        )
        row.selling_price = inherited if inherited is not None else DEFAULT_SELLING_PRICE
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _identity_clash(rows) -> str | None:
    """First (name, quality, shade, color) tuple shared by two of these rows.

    Mirrors the uq_inventory_identity index so a doomed bulk edit can be
    reported in plain language instead of surfacing as an IntegrityError.
    Nameless rows are skipped: the index leaves them alone, since a missing
    name never makes two rows the same product.
    """
    seen: set[tuple] = set()
    for r in rows:
        name = (r.name or "").strip()
        if not name:
            continue
        key = (name, r.quality, r.shade or "", r.color or "")
        if key in seen:
            parts = [r.quality, name]
            if key[2]:
                parts.append(f"درجة {key[2]}")
            if key[3]:
                parts.append(key[3])
            return " · ".join(p for p in parts if p)
        seen.add(key)
    return None


@router.put("/items/{iid}", response_model=ItemUpdateOut)
def update_item(iid: UUID, body: InventoryItemUpdate, db: Session = Depends(get_db)):
    row = db.get(InventoryItem, iid)
    if not row:
        raise HTTPException(404, "Item not found")

    # Work out what actually changed *before* touching the row, and remember the
    # reference we have to look siblings up by (it may itself be changing).
    original_reference = row.reference
    new_cost = Decimal(str(body.unit_cost))
    new_unit = body.unit or "m"

    # Colour travels with the group; shade and quantity stay per-item, since
    # shade is usually the thing telling siblings apart and quantity is
    # genuinely different stock. A colour change that would collapse two rows
    # onto the same identity is caught below rather than hitting the index.
    shared_changes = {}
    if body.reference != row.reference:
        shared_changes["reference"] = body.reference
    if body.quality != row.quality:
        shared_changes["quality"] = body.quality
    if body.color != row.color:
        shared_changes["color"] = body.color
    if body.name != row.name:
        shared_changes["name"] = body.name
    if new_unit != row.unit:
        shared_changes["unit"] = new_unit
    if new_cost != Decimal(str(row.avg_unit_cost_usd)):
        shared_changes["avg_unit_cost_usd"] = new_cost

    siblings: list[InventoryItem] = []
    if body.apply_to_reference and shared_changes:
        siblings = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.reference == original_reference,
                InventoryItem.id != row.id,
            )
            .all()
        )

    # What each row is about to become, worked out before anything is written
    # so a rename that collides can be turned into a merge instead of hitting
    # the unique index mid-flush.
    def intended(item: InventoryItem) -> dict:
        if item is row:
            return {"name": body.name, "quality": body.quality,
                    "color": body.color, "shade": body.shade}
        return {
            "name": shared_changes.get("name", item.name),
            "quality": shared_changes.get("quality", item.quality),
            "color": shared_changes.get("color", item.color),
            "shade": item.shade,
        }

    working = [row, *siblings]
    working_ids = [i.id for i in working]
    merges: list[tuple[InventoryItem, InventoryItem]] = []
    for item in working:
        target = find_by_identity(db, **intended(item), exclude_ids=working_ids)
        if target is not None:
            merges.append((item, target))

    merged_away = {src.id for src, _ in merges}
    survivors = [i for i in working if i.id not in merged_away]

    clash = _identity_clash([
        SimpleNamespace(**intended(i), reference=i.reference) for i in survivors
    ])
    if clash:
        raise HTTPException(
            400,
            f"لا يمكن تطبيق هذا التعديل على كل الأصناف: سيصبح صنفان بنفس "
            f"الاسم والطراز واللون والطيف ({clash}). "
            "غيّر الاسم أو اللون لكل صنف على حدة.",
        )

    # write the survivors, then fold the duplicates into whatever already owns
    # their identity
    for item in survivors:
        previous_unit = item.unit
        if item is row:
            _apply_item_fields(item, body, db)
        else:
            for field, value in shared_changes.items():
                setattr(item, field, value)
        if item.unit != previous_unit:
            item.reorder_level = default_reorder_level(item.unit)

    result = row
    for source, target in merges:
        absorb_item(db, source, target)
        if source is row:
            result = target

    db.commit()
    db.refresh(result)
    return ItemUpdateOut(
        item=InventoryItemOut.model_validate(result),
        updated_count=len(survivors),
        merged_count=len(merges),
    )


def _usage_counts(iid: UUID, db: Session) -> tuple[int, int]:
    """(receipt lines, sold lines) referencing this item."""
    received = db.query(func.count(InventoryReceiptItem.id)).filter(
        InventoryReceiptItem.inventory_item_id == iid
    ).scalar() or 0
    sold = db.query(func.count(SalesOrderItem.id)).filter(
        SalesOrderItem.inventory_item_id == iid
    ).scalar() or 0
    return int(received), int(sold)


@router.get("/items/{iid}/usage")
def item_usage(iid: UUID, db: Session = Depends(get_db)):
    """What a delete would take with it — lets the UI confirm before asking."""
    if not db.get(InventoryItem, iid):
        raise HTTPException(404, "Item not found")
    received, sold = _usage_counts(iid, db)
    return {"receipt_lines": received, "sold_lines": sold, "can_delete": sold == 0}


@router.post("/items/bulk-delete", response_model=BulkDeleteOut)
def bulk_delete_items(body: BulkDeleteIn, db: Session = Depends(get_db)):
    """Delete many items at once, skipping any that have been sold.

    Partial success is the normal outcome: the sold ones are reported back so
    the caller can say which survived and why, rather than failing the lot.
    """
    rows = db.query(InventoryItem).filter(InventoryItem.id.in_(body.ids)).all()
    deleted = 0
    receipt_lines = 0
    blocked: list[BlockedItem] = []

    for row in rows:
        received, sold = _usage_counts(row.id, db)
        if sold:
            blocked.append(BlockedItem(id=row.id, label=row.label, sold_lines=sold))
            continue
        receipt_lines += received
        db.delete(row)
        deleted += 1

    db.commit()
    return BulkDeleteOut(deleted=deleted, deleted_receipt_lines=receipt_lines, blocked=blocked)


@router.delete("/items/{iid}")
def delete_item(iid: UUID, db: Session = Depends(get_db)):
    row = db.get(InventoryItem, iid)
    if not row:
        raise HTTPException(404, "Item not found")

    received, sold = _usage_counts(iid, db)
    if sold:
        # An invoice's stored subtotal is never recomputed from its lines, so
        # removing a sold line would leave the فاتورة silently wrong.
        raise HTTPException(
            400,
            f"لا يمكن حذف صنف مباع — يظهر في {sold} سطر فاتورة. "
            "احذف الفاتورة أولًا إن أردت إزالته.",
        )

    # receipt lines cascade at the DB level
    db.delete(row)
    db.commit()
    return {"ok": True, "deleted_receipt_lines": received}


# ---- receipts ----

def _serialize_receipt(r: InventoryReceipt) -> ReceiptOut:
    return ReceiptOut(
        id=r.id,
        supplier_order_id=r.supplier_order_id,
        order_number=r.supplier_order.order_number if r.supplier_order else None,
        received_at=r.received_at,
        notes=r.notes,
        items=[ReceiptItemOut(
            id=i.id,
            inventory_item_id=i.inventory_item_id,
            item_label=i.item.label if i.item else None,
            qty=i.qty,
            unit_cost=i.unit_cost,
            currency=i.currency,
            fx_to_usd=i.fx_to_usd,
        ) for i in r.items],
    )


@router.get("/receipts", response_model=list[ReceiptOut])
def list_receipts(db: Session = Depends(get_db)):
    rows = db.query(InventoryReceipt).options(
        joinedload(InventoryReceipt.items).joinedload(InventoryReceiptItem.item),
    ).order_by(InventoryReceipt.received_at.desc()).all()
    return [_serialize_receipt(r) for r in rows]


def _line_cost(stated, item: InventoryItem) -> Decimal:
    """What one received line costs per unit.

    A line with no stated price keeps the item's existing cost, so receiving
    more of something already known never moves its average. Only a genuinely
    new item falls back to the placeholder — inventing a figure for a known
    item would blend a fiction into a real, purchase-order-derived cost.
    """
    if stated is not None:
        return Decimal(str(stated))
    current = Decimal(str(item.avg_unit_cost_usd or 0))
    return current if current > 0 else DEFAULT_UNIT_COST


@router.post("/receipts", response_model=ReceiptOut)
def create_receipt(body: ReceiptCreate, db: Session = Depends(get_db)):
    order = None
    if body.supplier_order_id:
        order = db.get(SupplierOrder, body.supplier_order_id)
        if not order:
            raise HTTPException(400, "أمر الشراء غير موجود")

    receipt = InventoryReceipt(supplier_order_id=body.supplier_order_id, notes=body.notes)
    if body.received_on:
        # Keep the current time-of-day so several receipts on one date still
        # sort newest-first; only the date itself comes from the form.
        now = datetime.now(tz=timezone.utc)
        receipt.received_at = datetime.combine(body.received_on, now.timetz())
    db.add(receipt)
    db.flush()
    for line in body.items:
        try:
            item = find_or_create_item(
                db,
                inventory_item_id=line.inventory_item_id,
                reference=line.reference,
                quality=line.quality,
                color=line.color,
                shade=line.shade,
                name=line.name,
                unit=line.unit,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))
        cost = _line_cost(line.unit_cost, item)
        fx_used = apply_receipt_line(
            db, item, Decimal(str(line.qty)), cost, "USD", None,
        )
        db.add(InventoryReceiptItem(
            receipt_id=receipt.id,
            inventory_item_id=item.id,
            qty=line.qty,
            unit_cost=cost,
            currency="USD",
            fx_to_usd=fx_used,
        ))

    # receiving against an order is what marks it shipped
    if order and order.status != "shipped":
        order.status = "shipped"
        order.shipped_at = datetime.now(tz=timezone.utc)

    db.commit()
    db.refresh(receipt)
    return _serialize_receipt(receipt)


# ---- spreadsheet import ----

def _fingerprint(rows: list[dict]) -> str:
    """Identify a packing list by what it says, not by its bytes.

    Hashing the parsed rows means a re-saved or re-exported file with identical
    contents is still recognised as the same list.
    """
    canonical = sorted(
        [
            str(r.get("reference") or ""), str(r.get("quality") or ""),
            str(r.get("color") or ""), str(r.get("shade") or ""),
            str(r.get("name") or ""), str(r.get("qty")), str(r.get("unit") or ""),
        ]
        for r in rows
    )
    return hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@router.post("/receipts/{rid}/import", response_model=ImportResult)
async def import_spreadsheet(
    rid: UUID,
    file: UploadFile = File(...),
    force: bool = False,
    db: Session = Depends(get_db),
):
    """Read a packing list into receipt lines, then discard the file.

    The bytes are parsed in memory and never stored: once the rows are in the
    database the spreadsheet holds nothing the database doesn't, and keeping it
    only consumed the object-storage quota.
    """
    receipt = db.get(InventoryReceipt, rid)
    if not receipt:
        raise HTTPException(404, "Receipt not found")

    content = await file.read()
    name = (file.filename or "").lower()
    if name.endswith((".xlsx", ".xlsm", ".xltx")):
        rows = parse_excel(content)
    elif name.endswith(".csv"):
        rows = parse_csv(content)
    else:
        raise HTTPException(400, "الملف يجب أن يكون Excel أو CSV")

    # These same contents may already have been read in, against this receipt or
    # another one. `force` is how the UI says the user looked and meant it — a
    # genuine repeat shipment can arrive with a byte-identical packing list.
    fingerprint = _fingerprint(rows)
    if not force:
        seen = (
            db.query(SpreadsheetImport)
            .filter(SpreadsheetImport.fingerprint == fingerprint)
            .order_by(SpreadsheetImport.imported_at.desc())
            .first()
        )
        if seen:
            raise HTTPException(
                409,
                f"هذه القائمة مستوردة من قبل ({seen.filename} — "
                f"{seen.imported_at:%Y-%m-%d}، {seen.rows_imported} سطر). "
                "استيرادها مرة أخرى سيضاعف الكميات.",
            )

    # Importing the same list twice would double every quantity without a word
    # of warning. Imported rows carry no name, so they never match an existing
    # item and cannot be deduplicated on identity — but a repeat shows up as
    # quantities this receipt already holds, which is enough to catch it.
    wanted = Counter(Decimal(str(r["qty"])) for r in rows)
    held = Counter(
        Decimal(str(q)) for (q,) in db.query(InventoryReceiptItem.qty)
        .filter(InventoryReceiptItem.receipt_id == rid).all()
    )
    if wanted and all(held[qty] >= n for qty, n in wanted.items()):
        raise HTTPException(
            400,
            "هذه الأسطر مستوردة بالفعل في هذا الاستلام. "
            "استيرادها مرة أخرى سيضاعف الكميات — أنشئ استلامًا جديدًا إن كانت شحنة أخرى.",
        )

    imported = 0
    skipped = 0
    for r in rows:
        try:
            item = find_or_create_item(
                db,
                reference=r.get("reference"),
                quality=r.get("quality"),
                color=r.get("color"),
                shade=r.get("shade"),
                name=r.get("name"),
                unit=r.get("unit"),
            )
        except ValueError:
            skipped += 1
            continue
        qty = Decimal(str(r["qty"]))
        unit_cost = _line_cost(r.get("unit_cost"), item)
        currency = r.get("currency", "USD")
        fx_used = apply_receipt_line(db, item, qty, unit_cost, currency, None)
        db.add(InventoryReceiptItem(
            receipt_id=rid,
            inventory_item_id=item.id,
            qty=qty,
            unit_cost=unit_cost,
            currency=currency,
            fx_to_usd=fx_used,
        ))
        imported += 1

    db.add(SpreadsheetImport(
        fingerprint=fingerprint,
        filename=file.filename or "",
        receipt_id=rid,
        rows_imported=imported,
    ))
    db.commit()
    return ImportResult(
        filename=file.filename or "",
        rows_found=len(rows),
        imported=imported,
        skipped=skipped,
    )
