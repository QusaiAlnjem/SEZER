"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { InventoryItem, ImportResult, SupplierOrder, OrderPage } from "@/types";
import { Modal } from "@/components/Modal";
import { OrderCostDialog, type OrderCosts } from "@/components/OrderCostDialog";
import { useConfirm } from "@/components/ConfirmDialog";
import { fmtQty, fmtMoney, today } from "@/lib/format";
import {
  Boxes, Plus, Trash2, Upload, PackagePlus, Search, AlertTriangle,
  Pencil, ChevronDown,
} from "lucide-react";

type ReceiptLine = {
  reference: string;
  quality: string;
  color: string;
  shade: string;
  name: string;
  qty: string;
  unit: string;
  unit_cost: string;
};
/** Goods start at $1/unit, not $0 — a zero cost would zero out stock value. */
const DEFAULT_UNIT_COST = "1";

/** Receipt lines start blank: an unpriced line keeps whatever the item already
 *  costs, so receiving more of a known product can't drag its average around. */
const emptyLine: ReceiptLine = {
  reference: "", quality: "", color: "", shade: "", name: "",
  qty: "", unit: "m", unit_cost: "",
};

const emptyItem = {
  reference: "", quality: "", color: "", shade: "", name: "",
  qty_on_hand: "", unit: "m", unit_cost: DEFAULT_UNIT_COST, selling_price: "",
};

/** Blank means "price unknown" — the server then keeps the item's own cost.
 *  A deliberate 0 is still sent as 0. */
function costValue(raw: string): number | undefined {
  return raw.trim() === "" ? undefined : Number(raw);
}

const UNITS = [
  { value: "m", label: "متر" },
  { value: "yd", label: "ياردة" },
  { value: "kg", label: "كيلوغرام" },
  { value: "pcs", label: "قطعة" },
];

/** "1547.000" -> "1547", "4.5000" -> "4.5" — Numeric() padding is noise in an input. */
function trimNum(v: string | number): string {
  const n = Number(v);
  return Number.isFinite(n) ? String(n) : String(v ?? "");
}

/** Rows fetched per page — the warehouse can run to thousands. */
const PAGE = 50;

export default function StoragePage() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [q, setQ] = useState("");
  const [lowOnly, setLowOnly] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const [showItemModal, setShowItemModal] = useState(false);
  const [editing, setEditing] = useState<InventoryItem | null>(null);
  const [applyToReference, setApplyToReference] = useState(false);
  // walking the user through naming rows a spreadsheet brought in unnamed
  const [naming, setNaming] = useState(false);
  const [itemForm, setItemForm] = useState({ ...emptyItem });

  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [receipt, setReceipt] = useState<{
    supplier_order_id: string; received_on: string; notes: string; items: ReceiptLine[];
  }>({
    supplier_order_id: "", received_on: today(), notes: "", items: [{ ...emptyLine }],
  });
  const [waitingOrders, setWaitingOrders] = useState<SupplierOrder[]>([]);
  // set after a receipt ships an order — prompts for that shipment's total
  const [costForOrder, setCostForOrder] = useState<SupplierOrder | null>(null);
  const [docFile, setDocFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const { ask, confirmUi } = useConfirm();

  /** Fetch from the start of the list, keeping however many pages are open.
   *
   *  The search runs server-side across every row, so a term still finds an
   *  item sitting far beyond the first page.
   */
  async function load(): Promise<InventoryItem[]> {
    setErr(null);
    try {
      const shown = Math.max(items.length, PAGE);
      const p = new URLSearchParams({ offset: "0", limit: String(shown) });
      if (q) p.set("q", q);
      if (lowOnly) p.set("low_stock", "true");
      const [rows, count] = await Promise.all([
        api.get<InventoryItem[]>(`/api/storage/items?${p}`),
        api.get<{ total: number }>(
          `/api/storage/items/count?${new URLSearchParams({
            ...(q ? { q } : {}),
            ...(lowOnly ? { low_stock: "true" } : {}),
          })}`,
        ),
      ]);
      setItems(rows);
      setTotalItems(count.total);
      // drop anything that filtering or deletion took off the list
      setSelected(prev => {
        const alive = new Set(rows.map(r => r.id));
        const next = new Set([...prev].filter(id => alive.has(id)));
        return next.size === prev.size ? prev : next;
      });
      return rows;
    } catch (e: any) { setErr(e.message); return []; }
  }

  async function loadMoreItems() {
    setLoadingMore(true);
    try {
      const p = new URLSearchParams({ offset: String(items.length), limit: String(PAGE) });
      if (q) p.set("q", q);
      if (lowOnly) p.set("low_stock", "true");
      const rows = await api.get<InventoryItem[]>(`/api/storage/items?${p}`);
      setItems(prev => [...prev, ...rows]);
    } catch (e: any) { setErr(e.message); } finally { setLoadingMore(false); }
  }

  // a new search starts from the first page again
  useEffect(() => { setItems([]); }, [q, lowOnly]);
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [q, lowOnly]);

  const unnamed = items.filter(i => !(i.name ?? "").trim());

  /** Open the next row still missing a name, or finish the pass.
   *
   *  Always driven from rows just fetched, never from `items`: a save that
   *  renames several rows at once (apply-to-reference) only shows up after the
   *  reload, and reacting to state that hasn't caught up would reopen the row
   *  that was just named.
   */
  function advanceNaming(rows: InventoryItem[]) {
    const next = rows.find(i => !(i.name ?? "").trim());
    if (next) {
      openEditItem(next);
    } else {
      setNaming(false);
      setShowItemModal(false);
      setNotice("تم تسمية كل الأصناف");
    }
  }

  // starts the pass; advancing from here on is done by saveItem
  useEffect(() => {
    if (naming) advanceNaming(items);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [naming]);

  // waiting orders feed the receipt form's order picker
  async function loadWaitingOrders() {
    try {
      const page = await api.get<OrderPage>("/api/suppliers/orders?status=waiting&limit=50");
      setWaitingOrders(page.orders);
    } catch { /* the picker just stays empty */ }
  }
  useEffect(() => { loadWaitingOrders(); }, []);

  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 4000);
    return () => clearTimeout(t);
  }, [notice]);

  function resetItemForm() {
    setItemForm({ ...emptyItem });
    setEditing(null);
    setApplyToReference(false);
  }

  function openNewItem() {
    resetItemForm();
    setShowItemModal(true);
  }

  function openEditItem(item: InventoryItem) {
    setItemForm({
      reference: item.reference,
      quality: item.quality,
      color: item.color ?? "",
      shade: item.shade ?? "",
      name: item.name ?? "",
      // Numeric() comes back as "1547.000" / "4.5000" — show it the way it was typed.
      qty_on_hand: trimNum(item.qty_on_hand),
      unit: item.unit,
      unit_cost: trimNum(item.avg_unit_cost_usd),
      selling_price: trimNum(item.selling_price),
    });
    setEditing(item);
    setApplyToReference(false);
    setShowItemModal(true);
  }

  async function saveItem() {
    setBusy(true);
    try {
      const payload = {
        reference: itemForm.reference.trim(),
        quality: itemForm.quality.trim(),
        color: itemForm.color || undefined,
        shade: itemForm.shade || undefined,
        name: itemForm.name.trim(),
        unit: itemForm.unit || "m",
        qty_on_hand: Number(itemForm.qty_on_hand || 0),
        unit_cost: costValue(itemForm.unit_cost),
        selling_price: itemForm.selling_price.trim() === ""
          ? undefined                      // blank: inherit, or leave as it is
          : Number(itemForm.selling_price),
      };

      if (editing) {
        const res = await api.put<{
          item: InventoryItem; updated_count: number; merged_count: number;
        }>(
          `/api/storage/items/${editing.id}`,
          { ...payload, apply_to_reference: applyToReference },
        );
        const parts: string[] = [];
        if (res.updated_count > 1) parts.push(`تم تحديث ${res.updated_count} أصناف`);
        if (res.merged_count) parts.push(`ودُمج ${res.merged_count} مع صنف موجود`);
        setNotice(parts.length ? parts.join(" ") : "تم حفظ التعديلات");
      } else {
        await api.post<InventoryItem>("/api/storage/items", payload);
      }

      resetItemForm();
      // wait for the reload before deciding what comes next, so a rename that
      // cleared several rows is actually reflected
      const rows = await load();
      if (naming) advanceNaming(rows);
      else setShowItemModal(false);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  async function submitReceipt() {
    setBusy(true);
    try {
      const payload = {
        supplier_order_id: receipt.supplier_order_id || undefined,
        received_on: receipt.received_on || undefined,
        notes: receipt.notes || undefined,
        items: receipt.items
          .filter(l => Number(l.qty) > 0 && l.reference.trim() && l.quality.trim() && l.name.trim())
          .map(l => ({
            reference: l.reference.trim(),
            quality: l.quality.trim(),
            color: l.color || undefined,
            shade: l.shade || undefined,
            name: l.name || undefined,
            qty: Number(l.qty),
            unit: l.unit || "m",
            unit_cost: costValue(l.unit_cost),
          })),
      };
      let receiptId: string | null = null;
      if (payload.items.length) {
        const r = await api.post<{ id: string }>("/api/storage/receipts", payload);
        receiptId = r.id;
      } else if (!docFile) {
        throw new Error("أضف صنفًا واحدًا على الأقل أو استورد ملف Excel");
      } else {
        const r = await api.post<{ id: string }>("/api/storage/receipts", {
          items: [],
          supplier_order_id: receipt.supplier_order_id || undefined,
          received_on: receipt.received_on || undefined,
          notes: receipt.notes,
        } as any);
        receiptId = r.id;
      }
      let imported: ImportResult | null = null;
      if (docFile && receiptId) {
        const send = (force: boolean) => {
          const form = new FormData();
          form.set("file", docFile);
          return api.form<ImportResult>(
            `/api/storage/receipts/${receiptId}/import${force ? "?force=true" : ""}`,
            form,
          );
        };
        try {
          imported = await send(false);
        } catch (e: any) {
          // 409: these contents have been read in before. Importing again would
          // double the quantities, so make the user say they meant it.
          if (e?.status !== 409) throw e;
          if (!(await ask(`${e.message}

هل تريد استيرادها على أي حال؟`))) {
            setShowReceiptModal(false);
            await load();
            return;
          }
          imported = await send(true);
        }
      }
      // the order has already shipped at this point — ask for its cost after
      const shipped = receipt.supplier_order_id
        ? waitingOrders.find(o => o.id === receipt.supplier_order_id) ?? null
        : null;
      if (imported) {
        setNotice(
          `تم استيراد ${imported.imported} سطر من ${imported.filename}` +
          (imported.skipped ? ` (تم تجاهل ${imported.skipped} سطرًا غير مكتمل)` : "")
        );
      } else if (shipped) {
        setNotice("تم حفظ الاستلام وتحويل أمر الشراء إلى shipped");
      }

      setReceipt({ supplier_order_id: "", received_on: today(), notes: "", items: [{ ...emptyLine }] });
      setDocFile(null);
      if (fileRef.current) fileRef.current.value = "";
      setShowReceiptModal(false);
      const rows = await load();
      loadWaitingOrders();   // the order just left the waiting list
      if (shipped) setCostForOrder(shipped);
      // a spreadsheet carries no names, so walk through them now
      else if (rows.some(i => !(i.name ?? "").trim())) setNaming(true);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  /** Record what the order the receipt just shipped actually cost.
   *
   *  The server spreads that cost over everything received against the order,
   *  so reload to pick up the unit costs it just worked out.
   */
  async function saveOrderCosts(costs: OrderCosts) {
    const order = costForOrder;
    setCostForOrder(null);
    if (!order) return;
    try {
      await api.patch(`/api/suppliers/orders/${order.id}/costs`, costs);
      setNotice(`تم تسجيل تكاليف الأمر ${order.order_number} وتوزيعها على تكلفة الأصناف`);
      load();
    } catch (e: any) { setErr(e.message); }
  }

  async function delItem(item: InventoryItem) {
    setErr(null);
    try {
      // Ask first what the delete would drag along, so the confirmation can say so.
      const usage = await api.get<{ receipt_lines: number; sold_lines: number; can_delete: boolean }>(
        `/api/storage/items/${item.id}/usage`
      );
      if (!usage.can_delete) {
        setErr(`لا يمكن حذف هذا الصنف — مباع في ${usage.sold_lines} سطر فاتورة. احذف الفاتورة أولًا إن أردت إزالته.`);
        return;
      }
      const extra = usage.receipt_lines > 0
        ? `\n\nسيتم أيضًا حذف ${usage.receipt_lines} سطر استلام مرتبط به.`
        : "";
      if (!(await ask(`حذف الصنف ${item.reference}${item.shade ? ` (درجة ${item.shade})` : ""}؟${extra}`))) return;
      await api.del(`/api/storage/items/${item.id}`);
      // the edit form would otherwise stay bound to a row that no longer exists
      if (editing?.id === item.id) { setShowItemModal(false); resetItemForm(); }
      load();
    } catch (e: any) { setErr(e.message); }
  }

  function toggleOne(id: string) {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected(prev => (prev.size === items.length ? new Set() : new Set(items.map(i => i.id))));
  }

  async function deleteSelected() {
    const ids = [...selected];
    if (!ids.length) return;
    if (!(await ask(`حذف ${ids.length} صنف؟ سيتم أيضًا حذف سطور الاستلام المرتبطة بها.`))) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await api.post<{
        deleted: number;
        deleted_receipt_lines: number;
        blocked: { id: string; label: string; sold_lines: number }[];
      }>("/api/storage/items/bulk-delete", { ids });

      setNotice(`تم حذف ${res.deleted} صنف` +
        (res.deleted_receipt_lines ? ` و${res.deleted_receipt_lines} سطر استلام` : ""));
      if (res.blocked.length) {
        setErr(
          `تعذّر حذف ${res.blocked.length} صنف لأنها مباعة: ` +
          res.blocked.map(b => b.label).join("، ")
        );
      }
      setSelected(new Set());
      load();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  const lowStock = useMemo(
    () => items.filter(i => Number(i.qty_on_hand) <= Number(i.reorder_level)).length,
    [items]
  );

  // how many rows share the reference being edited (including this one)
  const sameReferenceCount = useMemo(
    () => (editing ? items.filter(i => i.reference === editing.reference).length : 0),
    [items, editing]
  );

  const itemFormValid =
    itemForm.reference.trim() !== "" &&
    itemForm.quality.trim() !== "" &&
    itemForm.name.trim() !== "" &&
    itemForm.qty_on_hand !== "" &&
    Number(itemForm.qty_on_hand) >= 0;

  // the row arrived from a spreadsheet with no name — that is what we're here for
  const needsName = !!editing && !(editing.name ?? "").trim();

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-800 flex items-center gap-2">
            <Boxes size={22} className="text-brand" /> المستودع
          </h1>
          <p className="text-sm text-slate-500">سجّل استلام البضاعة يدويًا، أو ارفع قائمة تعبئة Excel لاستخراج الأصناف تلقائيًا</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button className="btn-ghost" onClick={openNewItem}><Plus size={16} /> صنف جديد</button>
          <button className="btn-primary" onClick={() => setShowReceiptModal(true)}><PackagePlus size={16} /> استلام بضاعة</button>
        </div>
      </header>

      {err ? <div className="card text-red-700 text-sm">{err}</div> : null}
      {notice ? <div className="card border-r-4 border-emerald-400 text-emerald-800 text-sm">{notice}</div> : null}

      {unnamed.length && !naming ? (
        <div className="card border-r-4 border-red-400 flex items-center gap-2 text-sm text-red-800 flex-wrap">
          <AlertTriangle size={16} className="shrink-0" />
          <span className="flex-1">
            <b className="num">{unnamed.length}</b> صنف بدون اسم — الاسم مطلوب لتمييز الأصناف عن بعضها
          </span>
          <button className="btn-ghost !py-1.5 !px-3" onClick={() => setNaming(true)}>
            <Pencil size={14} /> إضافة الأسماء
          </button>
        </div>
      ) : null}

      <div className="card">
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              className="input pr-9"
              placeholder="ابحث بأي شيء: رقم تعريفي، طراز، لون، طيف، اسم، وحدة، كمية..."
              value={q}
              onChange={e => setQ(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600 py-1.5 px-1">
            <input type="checkbox" className="w-4 h-4" aria-label="تحت الحد الأدنى فقط"
                   checked={lowOnly} onChange={e => setLowOnly(e.target.checked)} />
            <span>تحت الحد الأدنى فقط</span>
            {lowStock > 0 ? <span className="badge-amber ml-2"><AlertTriangle size={12} className="inline" /> {lowStock}</span> : null}
          </label>
        </div>

        {/* Bulk actions — only in the way once something is picked */}
        {selected.size > 0 ? (
          <div className="flex items-center gap-2 flex-wrap mb-3 rounded-xl bg-brand/5 border border-brand/20 px-3 py-2">
            <span className="text-sm font-semibold text-slate-700">
              تم تحديد {selected.size} من {items.length}
            </span>
            <div className="flex-1" />
            <button className="btn-ghost !py-1.5 text-slate-600" onClick={() => setSelected(new Set())}>
              إلغاء التحديد
            </button>
            <button className="btn-ghost !py-1.5 text-red-600" disabled={busy} onClick={deleteSelected}>
              <Trash2 size={14} /> حذف المحدد
            </button>
          </div>
        ) : null}

        {/* Mobile: cards. A 9-column table pushes quantity, cost and the row
            actions off a phone screen, where they are only reachable by
            side-scrolling the table. */}
        <div className="md:hidden space-y-2">
          {items.map(i => {
            const low = Number(i.qty_on_hand) <= Number(i.reorder_level);
            const picked = selected.has(i.id);
            return (
              <div
                key={i.id}
                className={`rounded-xl border p-3 ${
                  picked ? "border-brand bg-brand/5"
                    : low ? "border-amber-200 bg-amber-50/40" : "border-slate-200"
                }`}
              >
                <div className="flex gap-3">
                  <label className="p-1 -m-1 shrink-0">
                    <input
                      type="checkbox"
                      className="w-5 h-5"
                      aria-label="تحديد"
                      checked={picked}
                      onChange={() => toggleOne(i.id)}
                    />
                  </label>
                  <div className="flex-1 min-w-0">
                    <div className="num font-bold text-slate-800" dir="ltr">{i.reference}</div>
                    <div className="num text-xs text-slate-500" dir="ltr">{i.quality}</div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {i.shade ? <span className="badge-slate">درجة {i.shade}</span> : null}
                      {i.color ? <span className="badge-slate">{i.color}</span> : null}
                    </div>
                    {i.name ? <div className="text-xs text-slate-600 mt-1">{i.name}</div> : null}
                  </div>
                </div>
                <div className="mt-2 pt-2 border-t border-slate-100 flex items-center gap-3 text-xs">
                  <span>
                    المتوفر <span className="num font-bold">{fmtQty(i.qty_on_hand)} {i.unit}</span>
                    {low ? <AlertTriangle size={11} className="inline mr-1 text-amber-500" /> : null}
                  </span>
                  <span className="text-slate-500">
                    التكلفة <span className="num">{fmtMoney(i.avg_unit_cost_usd)}</span>
                  </span>
                  <span className="text-slate-500">
                    البيع <span className="num font-semibold">{fmtMoney(i.selling_price)}</span>
                  </span>
                  <div className="flex-1" />
                  <button className="btn-ghost !py-2 !px-3" onClick={() => openEditItem(i)} aria-label="تعديل">
                    <Pencil size={14} />
                  </button>
                  <button className="btn-ghost !py-2 !px-3 text-red-600" onClick={() => delItem(i)} aria-label="حذف">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })}
          {items.length === 0 ? <p className="py-6 text-center text-slate-500 text-sm">لا توجد أصناف.</p> : null}
        </div>

        <div className="hidden md:block overflow-x-auto scroll-thin">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-right text-slate-500">
                <Th>
                  <input
                    type="checkbox"
                    aria-label="تحديد الكل"
                    disabled={items.length === 0}
                    checked={items.length > 0 && selected.size === items.length}
                    ref={el => { if (el) el.indeterminate = selected.size > 0 && selected.size < items.length; }}
                    onChange={toggleAll}
                  />
                </Th>
                <Th>الرقم التعريفي</Th><Th>رقم الطراز</Th><Th>اللون / الطيف</Th>
                <Th>الاسم</Th><Th>المتوفر</Th><Th>تكلفة الوحدة</Th><Th>سعر البيع</Th><Th></Th>
              </tr>
            </thead>
            <tbody>
              {items.map(i => {
                const low = Number(i.qty_on_hand) <= Number(i.reorder_level);
                return (
                  <tr
                    key={i.id}
                    className={`border-t border-slate-100 ${
                      selected.has(i.id) ? "bg-brand/5" : low ? "bg-amber-50/40" : ""
                    }`}
                  >
                    <Td>
                      <input
                        type="checkbox"
                        aria-label="تحديد"
                        checked={selected.has(i.id)}
                        onChange={() => toggleOne(i.id)}
                      />
                    </Td>
                    <Td dir="ltr" className="num font-semibold">{i.reference}</Td>
                    <Td dir="ltr" className="num">{i.quality}</Td>
                    <Td>
                      {i.shade ? <span className="badge-slate">درجة {i.shade}</span> : null}
                      {i.color ? <span className="badge-slate">{i.color}</span> : null}
                      {!i.shade && !i.color ? "—" : null}
                    </Td>
                    <Td>{i.name || "—"}</Td>
                    <Td className="num">
                      {fmtQty(i.qty_on_hand)} {i.unit}
                      {low ? <AlertTriangle size={12} className="inline mr-1 text-amber-500" /> : null}
                    </Td>
                    <Td className="num">{fmtMoney(i.avg_unit_cost_usd)}</Td>
                    <Td className="num font-semibold">{fmtMoney(i.selling_price)}</Td>
                    <Td className="text-left">
                      <div className="flex gap-1 justify-end">
                        <button className="btn-ghost !py-1.5 !px-2" onClick={() => openEditItem(i)} aria-label="تعديل">
                          <Pencil size={14} />
                        </button>
                        <button className="btn-ghost !py-1.5 !px-2 text-red-600" onClick={() => delItem(i)} aria-label="حذف">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </Td>
                  </tr>
                );
              })}
              {items.length === 0 ? <tr><td colSpan={9} className="py-6 text-center text-slate-500 text-sm">لا توجد أصناف.</td></tr> : null}
            </tbody>
          </table>
        </div>

        {items.length < totalItems ? (
          <div className="pt-3 flex items-center gap-3 flex-wrap">
            <button className="btn-ghost !py-2 text-sm" disabled={loadingMore} onClick={loadMoreItems}>
              <ChevronDown size={14} /> {loadingMore ? "جارٍ التحميل..." : "تحميل المزيد"}
            </button>
            <span className="text-xs text-slate-500">
              <span className="num">{items.length}</span> من <span className="num">{totalItems}</span>
            </span>
          </div>
        ) : null}
      </div>

      {/* Asked after the receipt saved and shipped the order */}
      <OrderCostDialog
        open={costForOrder !== null}
        title="تكاليف الشحنة"
        order={costForOrder}
        saveLabel="حفظ"
        skipLabel="تخطٍ"
        onSave={saveOrderCosts}
        onSkip={() => setCostForOrder(null)}
        onDismiss={() => setCostForOrder(null)}
      />

      {confirmUi}

      {/* New / edit item */}
      <Modal
        open={showItemModal}
        onClose={() => {
          // closing mid-pass stops it; the banner is still there to resume from
          setNaming(false);
          setShowItemModal(false);
          resetItemForm();
        }}
        title={editing ? "تعديل الصنف" : "صنف جديد"}
        size="lg"
      >
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">الرقم التعريفي *</label>
              <input dir="ltr" className="input num" value={itemForm.reference}
                     onChange={e => setItemForm({ ...itemForm, reference: e.target.value })} />
            </div>
            <div>
              <label className="label">رقم الطراز *</label>
              <input dir="ltr" className="input num" value={itemForm.quality}
                     onChange={e => setItemForm({ ...itemForm, quality: e.target.value })} />
            </div>
            <div>
              <label className="label">اللون</label>
              <input className="input" value={itemForm.color}
                     onChange={e => setItemForm({ ...itemForm, color: e.target.value })} />
            </div>
            <div>
              <label className="label">رقم الطيف</label>
              <input dir="ltr" className="input num" placeholder="رقم فقط" value={itemForm.shade}
                     onChange={e => setItemForm({ ...itemForm, shade: e.target.value })} />
            </div>
            <div className="sm:col-span-2">
              <label className="label">
                الاسم *
                {needsName ? <span className="text-red-600 font-normal"> — مطلوب</span> : null}
              </label>
              <input
                className={`input ${
                  needsName && !itemForm.name.trim()
                    ? "border-red-400 bg-red-50 focus:border-red-500 focus:ring-red-100"
                    : ""
                }`}
                value={itemForm.name}
                autoFocus={needsName}
                onChange={e => setItemForm({ ...itemForm, name: e.target.value })}
              />
              {needsName ? (
                <p className="text-[11px] text-red-600 mt-1 leading-tight">
                  هذا الصنف جاء من ملف بدون اسم. الاسم يحدّد الصنف — إن طابق صنفًا موجودًا فسيُدمج معه ويحتفظ بسعره.
                </p>
              ) : null}
            </div>
            <div>
              <label className="label">الكمية المتوفرة *</label>
              <input dir="ltr" className="input num" value={itemForm.qty_on_hand}
                     onChange={e => setItemForm({ ...itemForm, qty_on_hand: e.target.value })} />
            </div>
            <div>
              <label className="label">الوحدة</label>
              <UnitSelect value={itemForm.unit} onChange={v => setItemForm({ ...itemForm, unit: v })} />
            </div>
            <div>
              <label className="label">سعر البيع (USD)</label>
              <input dir="ltr" className="input num" placeholder="1"
                     value={itemForm.selling_price}
                     onChange={e => setItemForm({ ...itemForm, selling_price: e.target.value })} />
              <p className="text-[11px] text-slate-400 mt-1 leading-tight">
                يُحدَّث تلقائيًا بآخر سعر بيع فعلي
              </p>
            </div>
            <div>
              <label className="label">تكلفة الوحدة (USD)</label>
              <input dir="ltr" className="input num" value={itemForm.unit_cost}
                     onChange={e => setItemForm({ ...itemForm, unit_cost: e.target.value })} />
              {editing?.logistics_per_unit != null && Number(editing.logistics_per_unit) > 0 ? (
                <p className="text-[11px] text-slate-500 mt-1 leading-tight">
                  تكلفة الشحن و الجمارك للوحدة{" "}
                  <span className="num font-semibold" dir="ltr">
                    {trimNum(editing.logistics_per_unit)}$
                  </span>
                </p>
              ) : null}
            </div>
          </div>

          {editing && sameReferenceCount > 1 ? (
            <label className="flex items-start gap-2 text-sm rounded-xl bg-slate-50 p-3 cursor-pointer">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={applyToReference}
                onChange={e => setApplyToReference(e.target.checked)}
              />
              <span>
                <span className="font-semibold">
                  تطبيق التعديلات على كل الأصناف بنفس الرقم التعريفي ({sameReferenceCount})
                </span>
                {needsName ? (
                  <span className="block text-xs text-slate-500 mt-0.5">
                    يملأ الاسم لكل الأصناف بهذا الرقم، فلا تُفتح نوافذها واحدة تلو الأخرى
                  </span>
                ) : null}
              </span>
            </label>
          ) : null}

          <button className="btn-primary w-full" disabled={busy || !itemFormValid} onClick={saveItem}>
            {editing ? "حفظ التعديلات" : "حفظ"}
          </button>
        </div>
      </Modal>

      {/* Receive goods */}
      <Modal open={showReceiptModal} onClose={() => setShowReceiptModal(false)} title="استلام بضاعة" size="xl">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">استلام لأمر شراء</label>
              <select
                className="select"
                value={receipt.supplier_order_id}
                onChange={e => setReceipt({ ...receipt, supplier_order_id: e.target.value })}
              >
                <option value="">— بدون أمر شراء —</option>
                {waitingOrders.map(o => (
                  <option key={o.id} value={o.id}>
                    {o.order_number} — {o.supplier_name}
                  </option>
                ))}
              </select>
              {waitingOrders.length === 0 ? (
                <p className="text-xs text-slate-500 mt-1">لا توجد أوامر شراء قيد الانتظار.</p>
              ) : null}
            </div>
            <div>
              <label className="label">التاريخ</label>
              <input
                type="date"
                className="input"
                value={receipt.received_on}
                onChange={e => setReceipt({ ...receipt, received_on: e.target.value })}
              />
            </div>
          </div>

          {/* One card per line — a 10-column table couldn't fit the modal without
              the fields colliding, and this stays readable on a phone too. */}
          <div className="space-y-3">
            {receipt.items.map((l, idx) => (
              <div key={idx} className="rounded-xl border border-slate-200 p-3">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold text-slate-500">صنف {idx + 1}</span>
                  {receipt.items.length > 1 ? (
                    <button
                      className="p-1 text-red-600 hover:bg-red-50 rounded"
                      onClick={() => removeReceiptLine(idx)}
                      aria-label="حذف السطر"
                    >
                      <Trash2 size={14} />
                    </button>
                  ) : null}
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="label">الرقم التعريفي *</label>
                    <input dir="ltr" className="input num" value={l.reference}
                           onChange={e => updateReceiptLine(idx, { reference: e.target.value })} />
                  </div>
                  <div>
                    <label className="label">رقم الطراز *</label>
                    <input dir="ltr" className="input num" value={l.quality}
                           onChange={e => updateReceiptLine(idx, { quality: e.target.value })} />
                  </div>
                  <div>
                    <label className="label">اللون</label>
                    <input className="input" value={l.color}
                           onChange={e => updateReceiptLine(idx, { color: e.target.value })} />
                  </div>
                  <div>
                    <label className="label">رقم الطيف</label>
                    <input dir="ltr" className="input num" value={l.shade}
                           onChange={e => updateReceiptLine(idx, { shade: e.target.value })} />
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <label className="label">الاسم *</label>
                    <input className="input" value={l.name}
                           onChange={e => updateReceiptLine(idx, { name: e.target.value })} />
                    <p className="text-[11px] text-slate-400 mt-1 leading-tight">
                      الاسم يحدّد الصنف — الأصناف بنفس الاسم والطراز واللون والطيف تُجمَّع معًا
                    </p>
                  </div>
                  <div>
                    <label className="label">الكمية *</label>
                    <input dir="ltr" className="input num" value={l.qty}
                           onChange={e => updateReceiptLine(idx, { qty: e.target.value })} />
                  </div>
                  <div>
                    <label className="label">الوحدة</label>
                    <UnitSelect value={l.unit} onChange={v => updateReceiptLine(idx, { unit: v })} />
                  </div>
                  <div>
                    <label className="label">تكلفة الوحدة (USD)</label>
                    <input dir="ltr" className="input num" placeholder="تلقائي"
                           value={l.unit_cost}
                           onChange={e => updateReceiptLine(idx, { unit_cost: e.target.value })} />
                    <p className="text-[11px] text-slate-400 mt-1 leading-tight">
                      اتركه فارغًا ليحتسب من تكلفة أمر الشراء، أو تبقى تكلفة الصنف كما هي
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <button className="btn-ghost" onClick={() => setReceipt({ ...receipt, items: [...receipt.items, { ...emptyLine }] })}>
            <Plus size={14} /> إضافة سطر
          </button>

          <div className="pt-3 border-t border-slate-100">
            <div className="font-bold mb-2">أو استورد قائمة تعبئة (Excel / CSV)</div>
            <p className="text-[11px] text-slate-400 mb-2 leading-tight">
              تُقرأ الأسطر وتُضاف للمخزون، ولا يُحتفظ بالملف نفسه
            </p>
            <input ref={fileRef} type="file" accept=".xlsx,.xlsm,.xltx,.csv"
                   onChange={e => setDocFile(e.target.files?.[0] || null)} className="text-sm" />
          </div>

          <div><label className="label">ملاحظات</label><textarea className="textarea" value={receipt.notes} onChange={e => setReceipt({ ...receipt, notes: e.target.value })} /></div>

          <button className="btn-primary w-full" disabled={busy} onClick={submitReceipt}>
            <Upload size={16} /> حفظ الاستلام
          </button>
        </div>
      </Modal>

    </div>
  );

  function updateReceiptLine(idx: number, patch: Partial<ReceiptLine>) {
    setReceipt(prev => ({ ...prev, items: prev.items.map((it, i) => i === idx ? { ...it, ...patch } : it) }));
  }
  function removeReceiptLine(idx: number) {
    setReceipt(prev => ({ ...prev, items: prev.items.length === 1 ? prev.items : prev.items.filter((_, i) => i !== idx) }));
  }
}

/** A datalist only *suggests* values, so the options went unnoticed — a real
 *  select shows them all. An unrecognised unit (from an import) is kept as its
 *  own option so editing an item can't silently change it. */
function UnitSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const known = UNITS.some(u => u.value === value);
  return (
    <select className="select" value={value} onChange={e => onChange(e.target.value)}>
      {UNITS.map(u => (
        <option key={u.value} value={u.value}>{u.label} ({u.value})</option>
      ))}
      {!known && value ? <option value={value}>{value}</option> : null}
    </select>
  );
}

function Th({ children }: { children?: React.ReactNode }) {
  return <th className="text-right font-medium px-3 py-2 whitespace-nowrap">{children}</th>;
}
function Td({ children, className = "", dir }: { children: React.ReactNode; className?: string; dir?: string }) {
  return <td dir={dir} className={`px-3 py-2 whitespace-nowrap ${className}`}>{children}</td>;
}
