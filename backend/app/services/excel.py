"""Parse an uploaded Excel/CSV of goods received into receipt-line dicts.

Two layouts are understood:

1. **Mill packing list** (the common case). A summary sheet lists one row per
   shade, e.g.::

       QUALITY   PROD. NO.   SHADE   ORDERED QTY(METER)   DISPATCHED QTY(METER)
       LOT-20    121771      1       1500                 1547
       LOT-20    121771      2       1500                 1535.9
       LOT-25    121776      BLACK   7000                 7080.9

   `SHADE` is either a shade number (kept as `shade`) or a colour name (kept
   as `color`). The dispatched quantity is what actually arrived, so it wins
   over the ordered quantity. The stock unit is read out of the header text,
   e.g. ``QTY(METER)`` -> ``m``.

2. **Flat sheet** with its own header row, using any of the column names in
   HEADER_MAP below (English or Arabic).

Every returned dict looks like::

    {"reference", "quality", "color", "shade", "name",
     "qty", "unit", "unit_cost", "currency"}
"""
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import List, Dict, Optional, Sequence


HEADER_MAP = {
    # الرقم التعريفي
    "reference": "reference", "ref": "reference", "prod. no.": "reference",
    "prod no": "reference", "prod.no.": "reference", "product no": "reference",
    "product number": "reference", "الرقم التعريفي": "reference", "المرجع": "reference",
    # رقم الطراز
    "quality": "quality", "lot": "quality", "رقم الطراز": "quality", "الطراز": "quality",
    # اللون
    "color": "color", "colour": "color", "اللون": "color", "لون": "color",
    # رقم الطيف
    "shade": "shade", "رقم الطيف": "shade", "الطيف": "shade",
    # الاسم
    "name": "name", "اسم": "name", "الاسم": "name", "الصنف": "name", "description": "name",
    # الكمية
    "qty": "qty", "quantity": "qty", "كمية": "qty", "الكمية": "qty",
    "dispatched qty": "qty", "الكمية المتوفرة": "qty",
    # الوحدة
    "unit": "unit", "الوحدة": "unit", "وحدة": "unit",
    # التكلفة
    "unit_cost": "unit_cost", "unit cost": "unit_cost", "price": "unit_cost",
    "سعر": "unit_cost", "السعر": "unit_cost", "تكلفة الوحدة": "unit_cost",
    "currency": "currency", "عملة": "currency", "العملة": "currency",
}

# Packing lists carry no prices, so imported goods start at $1/unit rather than
# $0 — a zero cost would silently drag COGS and stock value down to nothing.
DEFAULT_UNIT_COST = Decimal("1")

# Rows whose first cell starts with one of these are totals, not goods.
_TOTAL_MARKERS = ("sub total", "subtotal", "grand total", "total", "المجموع", "الإجمالي")

_UNIT_FROM_HEADER = (
    ("meter", "m"), ("metre", "m"), ("mtr", "m"), ("mtrs", "m"),
    ("yard", "yd"), ("yds", "yd"),
    ("pcs", "pcs"), ("piece", "pcs"), ("pc", "pcs"),
    ("kg", "kg"),
)


def _text(v) -> str:
    """Cell -> trimmed string, without Excel's trailing '.0' on whole numbers."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _norm(k) -> Optional[str]:
    key = _text(k).lower().rstrip(":.")
    key = " ".join(key.split())
    return HEADER_MAP.get(key)


def _to_decimal(v) -> Optional[Decimal]:
    s = _text(v).replace(",", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _is_total_row(first_cell) -> bool:
    s = _text(first_cell).lower()
    return any(s.startswith(m) for m in _TOTAL_MARKERS)


def _unit_from_header(*cells) -> str:
    blob = " ".join(_text(c).lower() for c in cells)
    for needle, unit in _UNIT_FROM_HEADER:
        if needle in blob:
            return unit
    return "m"


def _split_shade(raw) -> tuple[Optional[str], Optional[str]]:
    """SHADE cell -> (shade, color).

    A number is a shade ('3'); anything else is a colour name ('BLACK').
    """
    s = _text(raw)
    if not s:
        return None, None
    if _to_decimal(s) is not None:
        return s, None
    return None, s


# --------------------------------------------------------------------------
# layout 1: mill packing list
# --------------------------------------------------------------------------

def _find_summary_header(rows: Sequence[Sequence]) -> Optional[tuple[int, Dict[str, int]]]:
    """Locate the header row that carries QUALITY + SHADE + a quantity column."""
    for r_i, row in enumerate(rows):
        cols: Dict[str, int] = {}
        for c_i, cell in enumerate(row):
            s = _text(cell).lower()
            s = " ".join(s.split())
            if not s:
                continue
            if s.startswith("quality") or s.startswith("رقم الطراز"):
                cols.setdefault("quality", c_i)
            elif s.startswith("prod") or s.startswith("الرقم التعريفي"):
                cols.setdefault("reference", c_i)
            elif s.startswith("shade") or s.startswith("رقم الطيف"):
                cols.setdefault("shade", c_i)
            elif s.startswith("dispatched"):
                cols.setdefault("dispatched", c_i)
            elif s.startswith("ordered"):
                cols.setdefault("ordered", c_i)
        if "quality" in cols and "shade" in cols and ("dispatched" in cols or "ordered" in cols):
            return r_i, cols
    return None


def _parse_summary(rows: Sequence[Sequence]) -> List[Dict]:
    found = _find_summary_header(rows)
    if not found:
        return []
    header_i, cols = found
    header_row = rows[header_i]
    unit = _unit_from_header(
        header_row[cols["dispatched"]] if "dispatched" in cols else None,
        header_row[cols["ordered"]] if "ordered" in cols else None,
    )

    def cell(row, key):
        i = cols.get(key)
        return row[i] if i is not None and i < len(row) else None

    out: List[Dict] = []
    for row in rows[header_i + 1:]:
        if not row or all(v is None or _text(v) == "" for v in row):
            continue
        if _is_total_row(row[0] if row else None):
            continue

        quality = _text(cell(row, "quality"))
        reference = _text(cell(row, "reference"))
        if not quality and not reference:
            continue

        # dispatched is what actually arrived — prefer it over ordered
        qty = _to_decimal(cell(row, "dispatched"))
        if qty is None or qty <= 0:
            qty = _to_decimal(cell(row, "ordered"))
        if qty is None or qty <= 0:
            continue

        shade, color = _split_shade(cell(row, "shade"))
        out.append({
            "reference": reference or quality,
            "quality": quality or reference,
            "color": color,
            "shade": shade,
            "name": None,
            "qty": qty,
            "unit": unit,
            # a packing list carries no prices — leave it unknown so the
            # caller keeps whatever the item already costs
            "unit_cost": None,
            "currency": "USD",
        })
    return out


# --------------------------------------------------------------------------
# layout 2: flat sheet with its own header row
# --------------------------------------------------------------------------

def _parse_flat(rows: Sequence[Sequence]) -> List[Dict]:
    for r_i, row in enumerate(rows):
        cols = [_norm(h) for h in row]
        if not ("qty" in cols and ("reference" in cols or "quality" in cols)):
            continue
        out: List[Dict] = []
        for data in rows[r_i + 1:]:
            if _is_total_row(data[0] if data else None):
                continue
            record: Dict = {}
            for c, v in zip(cols, data):
                if not c or v is None or _text(v) == "":
                    continue
                record[c] = v
            qty = _to_decimal(record.get("qty"))
            if qty is None or qty <= 0:
                continue
            shade = _text(record.get("shade")) or None
            color = _text(record.get("color")) or None
            if shade and color is None:
                shade, color = _split_shade(shade)
            reference = _text(record.get("reference"))
            quality = _text(record.get("quality"))
            if not reference and not quality:
                continue
            # `or` would swallow a deliberate 0 in the file, so test for
            # absence. Left as None when the sheet has no price column.
            cost = _to_decimal(record.get("unit_cost"))
            out.append({
                "reference": reference or quality,
                "quality": quality or reference,
                "color": color,
                "shade": shade,
                "name": _text(record.get("name")) or None,
                "qty": qty,
                "unit": _text(record.get("unit")) or "m",
                "unit_cost": cost,
                "currency": (_text(record.get("currency")) or "USD").upper(),
            })
        if out:
            return out
    return []


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------

def _parse_rows(rows: Sequence[Sequence]) -> List[Dict]:
    return _parse_summary(rows) or _parse_flat(rows)


def parse_excel(content: bytes) -> List[Dict]:
    try:
        from openpyxl import load_workbook
    except ImportError:  # pragma: no cover
        return []

    wb = load_workbook(BytesIO(content), data_only=True)
    # A packing list keeps its per-shade totals on the SUMMARY sheet; try the
    # named one first so we never double-count the per-carton DETAIL rows.
    sheets = sorted(wb.worksheets, key=lambda s: 0 if "summary" in s.title.lower() else 1)
    for ws in sheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        parsed = _parse_rows(rows)
        if parsed:
            return parsed
    return []


def parse_csv(content: bytes) -> List[Dict]:
    import csv, io
    text = content.decode("utf-8-sig", errors="replace")
    rows = [r for r in csv.reader(io.StringIO(text))]
    return _parse_rows(rows)
