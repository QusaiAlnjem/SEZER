"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Supplier, SupplierOrder, OrderPage, InventoryItem } from "@/types";
import { Modal } from "@/components/Modal";
import { OrderCostDialog, type OrderCosts } from "@/components/OrderCostDialog";
import { useConfirm } from "@/components/ConfirmDialog";
import { itemLabel } from "@/components/ItemPicker";
import { fmtDate, fmtMoney, fmtTotal, today } from "@/lib/format";
import {
  Truck, Plus, Trash2, Search, CheckCircle2, Clock, Phone, Mail,
  History, ChevronDown, PackageCheck, Building2, Pencil,
  ArrowDownToLine, Eraser, Check, ListTree,
} from "lucide-react";

const PAGE = 6;
const SUPPLIER_PAGE = 10;   // the rest are a click away; search covers them all

type ProductDraft = { name: string; quality: string; color: string; shade: string };
const emptyProduct: ProductDraft = { name: "", quality: "", color: "", shade: "" };

type ProductLike = { name?: string | null; quality?: string | null; color?: string | null; shade?: string | null };

const productKey = (p: ProductLike) =>
  [p.name, p.quality, p.color, p.shade].map(v => (v ?? "").trim().toLowerCase()).join("|");

const isBlankProduct = (p: ProductDraft) => !(p.name || p.quality || p.color || p.shade);

const productLabel = (p: ProductLike) =>
  [p.name, p.quality, p.color, p.shade].filter(Boolean).join(" · ");

/** A storage item as a PO line. الرقم التعريفي has no column here, so it is dropped. */
const asProduct = (i: InventoryItem): ProductDraft => ({
  name: i.name ?? "",
  quality: i.quality ?? "",
  color: i.color ?? "",
  shade: i.shade ?? "",
});

type HistoryState = { orders: SupplierOrder[]; hasMore: boolean; total: number; loading: boolean };

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [orders, setOrders] = useState<SupplierOrder[]>([]);
  const [ordersMore, setOrdersMore] = useState(false);
  const [ordersTotal, setOrdersTotal] = useState(0);
  const [q, setQ] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  // supplier form
  const [showSupplier, setShowSupplier] = useState(false);
  const [sup, setSup] = useState({ name: "", company_name: "", email: "" });
  const [phones, setPhones] = useState<string[]>([""]);

  // order form
  const [showOrder, setShowOrder] = useState(false);
  const [order, setOrder] = useState({
    supplier_id: "", order_date: today(), shipping_date: "",
    products: [{ ...emptyProduct }] as ProductDraft[],
  });

  // storage items, offered for re-use so PO lines don't have to be retyped
  const [stock, setStock] = useState<InventoryItem[]>([]);
  const [stockLoading, setStockLoading] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerQuery, setPickerQuery] = useState("");

  // per-supplier history, loaded only when asked for
  const [history, setHistory] = useState<Record<string, HistoryState>>({});

  // cost prompt: "ship" asks before shipping, "edit" corrects what is already stored
  const [costFor, setCostFor] = useState<{ order: SupplierOrder; mode: "ship" | "edit" } | null>(null);
  // the order whose products and costs are being read
  const [details, setDetails] = useState<SupplierOrder | null>(null);
  const { ask, confirmUi } = useConfirm();
  const [suppliersShown, setSuppliersShown] = useState(SUPPLIER_PAGE);

  async function load() {
    setErr(null);
    try {
      const query = q.trim() ? `?q=${encodeURIComponent(q.trim())}` : "";
      const [s, o] = await Promise.all([
        api.get<Supplier[]>(`/api/suppliers${query}`),
        api.get<OrderPage>(`/api/suppliers/orders${query}${query ? "&" : "?"}offset=0&limit=${PAGE}`),
      ]);
      setSuppliers(s);
      setOrders(o.orders);
      setOrdersMore(o.has_more);
      setOrdersTotal(o.total);
      setHistory({});          // stale once the filter changes
    } catch (e: any) { setErr(e.message); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [q]);

  // a new search starts the supplier list over
  useEffect(() => { setSuppliersShown(SUPPLIER_PAGE); }, [q]);

  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 4000);
    return () => clearTimeout(t);
  }, [notice]);

  useEffect(() => {
    setPickerOpen(false);
    setPickerQuery("");
    if (!showOrder) return;
    let cancelled = false;
    setStockLoading(true);
    api.get<InventoryItem[]>("/api/storage/items")
      .then(r => { if (!cancelled) setStock(r); })
      .catch(() => { if (!cancelled) setStock([]); })
      .finally(() => { if (!cancelled) setStockLoading(false); });
    return () => { cancelled = true; };
  }, [showOrder]);

  async function loadMoreOrders() {
    setLoadingMore(true);
    try {
      const query = q.trim() ? `?q=${encodeURIComponent(q.trim())}&` : "?";
      const page = await api.get<OrderPage>(`/api/suppliers/orders${query}offset=${orders.length}&limit=${PAGE}`);
      setOrders(prev => [...prev, ...page.orders]);
      setOrdersMore(page.has_more);
    } catch (e: any) { setErr(e.message); } finally { setLoadingMore(false); }
  }

  async function loadHistory(supplierId: string, reset = false) {
    const current = history[supplierId];
    const offset = reset || !current ? 0 : current.orders.length;
    setHistory(h => ({
      ...h,
      [supplierId]: { orders: current && !reset ? current.orders : [], hasMore: false, total: current?.total ?? 0, loading: true },
    }));
    try {
      const page = await api.get<OrderPage>(`/api/suppliers/${supplierId}/orders?offset=${offset}&limit=${PAGE}`);
      setHistory(h => {
        const prev = reset ? [] : (h[supplierId]?.orders ?? []);
        return {
          ...h,
          [supplierId]: {
            orders: [...prev, ...page.orders],
            hasMore: page.has_more,
            total: page.total,
            loading: false,
          },
        };
      });
    } catch (e: any) {
      setErr(e.message);
      setHistory(h => ({ ...h, [supplierId]: { ...(h[supplierId] ?? { orders: [], total: 0, hasMore: false }), loading: false } }));
    }
  }

  function resetSupplierForm() {
    setSup({ name: "", company_name: "", email: "" });
    setPhones([""]);
  }

  async function saveSupplier() {
    setBusy(true);
    try {
      await api.post<Supplier>("/api/suppliers", {
        name: sup.name.trim(),
        company_name: sup.company_name || undefined,
        email: sup.email || undefined,
        phones: phones.map(p => p.trim()).filter(Boolean),
      });
      resetSupplierForm();
      setShowSupplier(false);
      setNotice("تم حفظ المورد");
      load();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  async function saveOrder() {
    setBusy(true);
    try {
      await api.post("/api/suppliers/orders", {
        supplier_id: order.supplier_id,
        order_date: order.order_date,
        shipping_date: order.shipping_date,
        products: order.products
          .filter(p => !isBlankProduct(p))
          .map(p => ({
            name: p.name || undefined,
            quality: p.quality || undefined,
            color: p.color || undefined,
            shade: p.shade || undefined,
          })),
      });
      setOrder({ supplier_id: "", order_date: today(), shipping_date: "", products: [{ ...emptyProduct }] });
      setShowOrder(false);
      setNotice("تم حفظ أمر الشراء");
      load();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  function applyOrder(updated: SupplierOrder) {
    setOrders(prev => prev.map(x => (x.id === updated.id ? updated : x)));
    setDetails(d => (d && d.id === updated.id ? updated : d));
    setHistory(h => {
      const entry = h[updated.supplier_id];
      if (!entry) return h;
      return {
        ...h,
        [updated.supplier_id]: { ...entry, orders: entry.orders.map(x => (x.id === updated.id ? updated : x)) },
      };
    });
  }

  /** Ship the order, recording what it cost in the same write. */
  async function shipOrder(o: SupplierOrder, costs: OrderCosts | null) {
    setBusy(true);
    try {
      const updated = await api.patch<SupplierOrder>(`/api/suppliers/orders/${o.id}/status`, {
        status: "shipped",
        ...(costs ?? { shipment_cost: null }),
      });
      applyOrder(updated);
      setNotice(costs === null ? "تم الشحن بدون تسجيل تكلفة" : "تم الشحن وتسجيل التكاليف");
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); setCostFor(null); }
  }

  /** Fill in or correct the costs on an order that already shipped. */
  async function saveCosts(o: SupplierOrder, costs: OrderCosts | null) {
    setBusy(true);
    try {
      const updated = await api.patch<SupplierOrder>(
        `/api/suppliers/orders/${o.id}/costs`,
        costs ?? { shipment_cost: null },
      );
      applyOrder(updated);
      setNotice(costs === null ? "تم مسح التكاليف" : "تم حفظ التكاليف");
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); setCostFor(null); }
  }

  async function deleteOrder(o: SupplierOrder) {
    if (!(await ask(`حذف أمر الشراء ${o.order_number}؟`))) return;
    try {
      await api.del(`/api/suppliers/orders/${o.id}`);
      // anything still pointing at the deleted order would keep its modal open
      setCostFor(c => (c?.order.id === o.id ? null : c));
      setDetails(d => (d?.id === o.id ? null : d));
      load();
    } catch (e: any) { setErr(e.message); }
  }

  async function deleteSupplier(s: Supplier) {
    const extra = s.order_count ? `\n\nسيتم أيضًا حذف ${s.order_count} أمر شراء وسجلها.` : "";
    if (!(await ask(`حذف المورد ${s.name}؟${extra}`))) return;
    try {
      await api.del(`/api/suppliers/${s.id}`);
      setCostFor(c => (c?.order.supplier_id === s.id ? null : c));
      setDetails(d => (d?.supplier_id === s.id ? null : d));
      load();
    } catch (e: any) { setErr(e.message); }
  }

  const orderValid = order.supplier_id && order.order_date && order.shipping_date;
  const draftKeys = new Set(order.products.filter(p => !isBlankProduct(p)).map(productKey));

  // newest additions first — those are the ones most likely to be reordered
  const stockMatches = (() => {
    const terms = pickerQuery.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const pool = terms.length
      ? stock.filter(i => {
          const hay = [i.reference, i.quality, i.color, i.shade, i.name, i.unit]
            .filter(Boolean).join(" ").toLowerCase();
          return terms.every(t => hay.includes(t));
        })
      : stock;
    return [...pool]
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .slice(0, 50);
  })();

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-800 flex items-center gap-2">
            <Truck size={22} className="text-brand" /> الموردون وأوامر الشراء
          </h1>
          <p className="text-sm text-slate-500">سجّل الموردين ومنتجاتهم، وتابع أوامر الشراء حتى الشحن</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button className="btn-ghost" onClick={() => setShowSupplier(true)}><Plus size={16} /> مورد جديد</button>
          <button className="btn-primary" onClick={() => setShowOrder(true)} disabled={suppliers.length === 0}>
            <Plus size={16} /> أمر شراء جديد
          </button>
        </div>
      </header>

      {err ? <div className="card text-red-700 text-sm">{err}</div> : null}
      {notice ? <div className="card border-r-4 border-emerald-400 text-emerald-800 text-sm">{notice}</div> : null}

      <div className="card">
        <div className="relative">
          <Search size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className="input pr-9"
            placeholder="ابحث بأي شيء: اسم المورد، الشركة، الهاتف، رقم الأمر، الطراز، اللون..."
            value={q}
            onChange={e => setQ(e.target.value)}
          />
        </div>
      </div>

      {/* Orders */}
      <div className="card">
        <div className="font-bold mb-3">أوامر الشراء {ordersTotal ? `(${ordersTotal})` : ""}</div>
        {orders.length === 0 ? (
          <p className="text-sm text-slate-500">لا توجد أوامر شراء.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {orders.map(o => (
              <OrderCard
                key={o.id}
                order={o}
                onShip={() => setCostFor({ order: o, mode: "ship" })}
                onEditCost={() => setCostFor({ order: o, mode: "edit" })}
                onDetails={() => setDetails(o)}
                onDelete={deleteOrder}
              />
            ))}
          </div>
        )}
        {ordersMore ? (
          <button className="btn-ghost mt-3" disabled={loadingMore} onClick={loadMoreOrders}>
            <ChevronDown size={14} /> {loadingMore ? "جارٍ التحميل..." : "تحميل المزيد"}
          </button>
        ) : null}
      </div>

      {/* Suppliers */}
      <div className="card">
        <div className="font-bold mb-3">الموردون ({suppliers.length})</div>
        {suppliers.length === 0 ? (
          <p className="text-sm text-slate-500">لا يوجد موردون بعد.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {suppliers.slice(0, suppliersShown).map(s => {
              const h = history[s.id];
              return (
                <div key={s.id} className="rounded-xl border border-slate-200 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-bold text-slate-800">{s.name}</div>
                      {s.company_name ? (
                        <div className="text-xs text-slate-500 flex items-center gap-1">
                          <Building2 size={12} /> {s.company_name}
                        </div>
                      ) : null}
                    </div>
                    <button className="btn-ghost !py-2 !px-3 text-red-600" onClick={() => deleteSupplier(s)} aria-label="حذف">
                      <Trash2 size={14} />
                    </button>
                  </div>

                  <div className="mt-2 space-y-1 text-xs text-slate-600">
                    {s.phones.map((p, i) => (
                      <div key={i} className="flex items-center gap-1">
                        <Phone size={12} className="text-slate-400" />
                        <span dir="ltr" className="num">{p}</span>
                      </div>
                    ))}
                    {s.email ? (
                      <div className="flex items-center gap-1">
                        <Mail size={12} className="text-slate-400" />
                        <span dir="ltr">{s.email}</span>
                      </div>
                    ) : null}
                  </div>

                  <div className="mt-3 pt-3 border-t border-slate-100">
                    {!h ? (
                      <button className="btn-ghost !py-1.5 text-sm" onClick={() => loadHistory(s.id, true)}>
                        <History size={14} /> عرض السجل ({s.order_count})
                      </button>
                    ) : (
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-slate-500">السجل ({h.total})</div>
                        {h.orders.map(o => (
                          <div key={o.id} className="flex items-center justify-between gap-2 text-xs rounded-lg bg-slate-50 px-2 py-1.5">
                            <span className="num" dir="ltr">{o.order_number}</span>
                            <span className="text-slate-500">{fmtDate(o.order_date)}</span>
                            <StatusBadge status={o.status} small />
                          </div>
                        ))}
                        {h.loading ? <div className="text-xs text-slate-400">جارٍ التحميل...</div> : null}
                        {h.hasMore && !h.loading ? (
                          <button className="btn-ghost !py-1 text-xs" onClick={() => loadHistory(s.id)}>
                            <ChevronDown size={12} /> تحميل المزيد
                          </button>
                        ) : null}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {suppliers.length > suppliersShown ? (
          <button
            className="btn-ghost !py-2 mt-3 text-sm"
            onClick={() => setSuppliersShown(n => n + SUPPLIER_PAGE)}
          >
            <ChevronDown size={14} /> عرض المزيد ({suppliers.length - suppliersShown})
          </button>
        ) : null}
      </div>

      {/* Costs — asked before shipping, or when correcting later */}
      <OrderCostDialog
        open={costFor !== null}
        title={costFor?.mode === "ship" ? "تكاليف الشحنة" : "تعديل تكاليف الشحنة"}
        order={costFor?.order}
        prefill={costFor?.mode === "edit"}
        saveLabel="حفظ"
        skipLabel={costFor?.mode === "ship" ? "شحن بدون تكلفة" : "بدون تكلفة"}
        busy={busy}
        onSave={costs => {
          if (!costFor) return;
          costFor.mode === "ship" ? shipOrder(costFor.order, costs) : saveCosts(costFor.order, costs);
        }}
        onSkip={() => {
          if (!costFor) return;
          costFor.mode === "ship" ? shipOrder(costFor.order, null) : saveCosts(costFor.order, null);
        }}
        onDismiss={() => {
          // Closing the "before shipping" prompt still ships, just without costs.
          if (costFor?.mode === "ship") shipOrder(costFor.order, null);
          else setCostFor(null);
        }}
      />

      <OrderDetailsModal order={details} onClose={() => setDetails(null)} />

      {confirmUi}

      {/* New supplier */}
      <Modal open={showSupplier} onClose={() => { setShowSupplier(false); resetSupplierForm(); }} title="مورد جديد" size="lg">
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">الاسم *</label>
              <input className="input" value={sup.name} onChange={e => setSup({ ...sup, name: e.target.value })} />
            </div>
            <div>
              <label className="label">اسم الشركة</label>
              <input className="input" value={sup.company_name} onChange={e => setSup({ ...sup, company_name: e.target.value })} />
            </div>
          </div>

          <div>
            <label className="label">رقم الهاتف</label>
            <div className="space-y-2">
              {phones.map((p, i) => (
                <div key={i} className="flex gap-2">
                  <input
                    dir="ltr" className="input num" placeholder="+90..."
                    value={p}
                    onChange={e => setPhones(prev => prev.map((x, xi) => (xi === i ? e.target.value : x)))}
                  />
                  {phones.length > 1 ? (
                    <button className="btn-ghost !px-2 text-red-600"
                            onClick={() => setPhones(prev => prev.filter((_, xi) => xi !== i))}>
                      <Trash2 size={14} />
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
            <button className="btn-ghost !py-1.5 mt-2 text-sm" onClick={() => setPhones(prev => [...prev, ""])}>
              <Plus size={14} /> إضافة رقم آخر
            </button>
          </div>

          <div>
            <label className="label">البريد الإلكتروني</label>
            <input dir="ltr" className="input" value={sup.email} onChange={e => setSup({ ...sup, email: e.target.value })} />
          </div>

          <button className="btn-primary w-full" disabled={busy || !sup.name.trim()} onClick={saveSupplier}>حفظ</button>
        </div>
      </Modal>

      {/* New order */}
      <Modal open={showOrder} onClose={() => setShowOrder(false)} title="أمر شراء جديد" size="lg">
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="label">المورد *</label>
              <select className="select" value={order.supplier_id}
                      onChange={e => setOrder({ ...order, supplier_id: e.target.value })}>
                <option value="">— اختر —</option>
                {suppliers.map(s => (
                  <option key={s.id} value={s.id}>{s.company_name ? `${s.name} — ${s.company_name}` : s.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">تاريخ الطلب *</label>
              <input type="date" className="input" value={order.order_date}
                     onChange={e => setOrder({ ...order, order_date: e.target.value })} />
            </div>
            <div>
              <label className="label">تاريخ الشحن *</label>
              <input type="date" className="input" value={order.shipping_date}
                     onChange={e => setOrder({ ...order, shipping_date: e.target.value })} />
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100">
            <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
              <div className="font-bold text-sm">المنتجات <span className="font-normal text-slate-500">(اختياري)</span></div>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <button
                    className="btn-ghost !py-1.5 !px-3 text-sm"
                    title="تعبئة من المخزون"
                    onClick={() => setPickerOpen(v => !v)}
                  >
                    <ArrowDownToLine size={14} /> من المخزون
                    <ChevronDown size={14} className={`transition ${pickerOpen ? "rotate-180" : ""}`} />
                  </button>
                  {pickerOpen ? (
                    <>
                      <div className="fixed inset-0 z-10" onClick={() => setPickerOpen(false)} />
                      <div className="absolute z-20 right-0 mt-1 w-80 rounded-xl border border-slate-200 bg-white shadow-xl p-1">
                        <div className="relative p-1">
                          <Search size={13} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                          <input
                            className="input !py-1.5 pr-8 text-xs"
                            placeholder="ابحث في المخزون..."
                            value={pickerQuery}
                            autoFocus
                            onChange={e => setPickerQuery(e.target.value)}
                          />
                        </div>
                        <div className="max-h-56 overflow-auto scroll-thin">
                          {stockLoading ? (
                            <div className="px-2 py-3 text-xs text-slate-400">جارٍ التحميل...</div>
                          ) : stockMatches.length === 0 ? (
                            <div className="px-2 py-3 text-xs text-slate-400">
                              {stock.length === 0 ? "لا توجد أصناف في المخزون." : "لا توجد نتائج."}
                            </div>
                          ) : (
                            <>
                              <button
                                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs font-semibold text-brand hover:bg-slate-50"
                                onClick={() => { fillFromStock(stockMatches); setPickerOpen(false); }}
                              >
                                <ArrowDownToLine size={13} /> إضافة الكل ({stockMatches.length})
                              </button>
                              <div className="my-1 border-t border-slate-100" />
                              {stockMatches.map(i => {
                                const added = draftKeys.has(productKey(asProduct(i)));
                                return (
                                  <button
                                    key={i.id}
                                    disabled={added}
                                    className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-right hover:bg-slate-50 disabled:opacity-50 disabled:hover:bg-transparent"
                                    onClick={() => fillFromStock([i])}
                                  >
                                    {added
                                      ? <Check size={13} className="shrink-0 text-emerald-600" />
                                      : <Plus size={13} className="shrink-0 text-slate-400" />}
                                    <span className="truncate">{itemLabel(i)}</span>
                                  </button>
                                );
                              })}
                            </>
                          )}
                        </div>
                      </div>
                    </>
                  ) : null}
                </div>
                <button
                  className="btn-ghost !py-1.5 !px-3 text-sm text-red-600 disabled:opacity-50"
                  disabled={draftKeys.size === 0}
                  onClick={clearProducts}
                >
                  <Eraser size={14} /> مسح الكل
                </button>
              </div>
            </div>
            <div className="space-y-3">
              {order.products.map((p, idx) => (
                <div key={idx} className="rounded-xl border border-slate-200 p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-500">منتج {idx + 1}</span>
                    {order.products.length > 1 ? (
                      <button className="p-1 text-red-600 hover:bg-red-50 rounded"
                              onClick={() => setOrder(o => ({ ...o, products: o.products.filter((_, i) => i !== idx) }))}>
                        <Trash2 size={14} />
                      </button>
                    ) : null}
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    <div>
                      <label className="label">الاسم</label>
                      <input className="input" value={p.name}
                             onChange={e => updateProduct(idx, { name: e.target.value })} />
                    </div>
                    <div>
                      <label className="label">رقم الطراز</label>
                      <input dir="ltr" className="input num" value={p.quality}
                             onChange={e => updateProduct(idx, { quality: e.target.value })} />
                    </div>
                    <div>
                      <label className="label">اللون</label>
                      <input className="input" value={p.color}
                             onChange={e => updateProduct(idx, { color: e.target.value })} />
                    </div>
                    <div>
                      <label className="label">رقم الطيف</label>
                      <input dir="ltr" className="input num" value={p.shade}
                             onChange={e => updateProduct(idx, { shade: e.target.value })} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <button className="btn-ghost !py-1.5 mt-2 text-sm"
                    onClick={() => setOrder(o => ({ ...o, products: [...o.products, { ...emptyProduct }] }))}>
              <Plus size={14} /> إضافة منتج
            </button>
          </div>

          <button className="btn-primary w-full" disabled={busy || !orderValid} onClick={saveOrder}>حفظ الأمر</button>
        </div>
      </Modal>
    </div>
  );

  function updateProduct(idx: number, patch: Partial<ProductDraft>) {
    setOrder(o => ({ ...o, products: o.products.map((p, i) => (i === idx ? { ...p, ...patch } : p)) }));
  }

  /** Append storage items as lines, dropping the empty slots and any duplicates. */
  function fillFromStock(picked: InventoryItem[]) {
    setOrder(o => {
      const products = o.products.filter(p => !isBlankProduct(p));
      const seen = new Set(products.map(productKey));
      for (const i of picked) {
        const draft = asProduct(i);
        const key = productKey(draft);
        if (seen.has(key)) continue;
        seen.add(key);
        products.push(draft);
      }
      return { ...o, products: products.length ? products : [{ ...emptyProduct }] };
    });
  }

  function clearProducts() {
    setOrder(o => ({ ...o, products: [{ ...emptyProduct }] }));
    setPickerOpen(false);
  }
}

function StatusBadge({ status, small }: { status: "waiting" | "shipped"; small?: boolean }) {
  if (status === "shipped") {
    return (
      <span className={`badge-green inline-flex items-center gap-1 ${small ? "text-[11px]" : ""}`}>
        <CheckCircle2 size={small ? 11 : 13} /> shipped
      </span>
    );
  }
  return (
    <span className={`badge-amber inline-flex items-center gap-1 ${small ? "text-[11px]" : ""}`}>
      <Clock size={small ? 11 : 13} /> قيد الانتظار
    </span>
  );
}

function OrderCard({
  order, onShip, onEditCost, onDetails, onDelete,
}: {
  order: SupplierOrder;
  onShip: (o: SupplierOrder) => void;
  onEditCost: (o: SupplierOrder) => void;
  onDetails: (o: SupplierOrder) => void;
  onDelete: (o: SupplierOrder) => void;
}) {
  return (
    <div className={`rounded-xl border p-3 ${order.status === "shipped" ? "border-emerald-200 bg-emerald-50/30" : "border-slate-200"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="num font-bold text-slate-800" dir="ltr">{order.order_number}</div>
          <div className="text-sm text-slate-700 truncate">{order.supplier_name}</div>
          {order.supplier_company ? (
            <div className="text-xs text-slate-500 truncate">{order.supplier_company}</div>
          ) : null}
        </div>
        <StatusBadge status={order.status} />
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
        <div>الطلب: <span className="num">{fmtDate(order.order_date)}</span></div>
        <div>الشحن: <span className="num">{fmtDate(order.shipping_date)}</span></div>
        <div className="col-span-2 flex items-center gap-1">
          <span>التكلفة الإجمالية:</span>
          {hasCosts(order) ? (
            <span className="num font-semibold text-slate-800" dir="ltr">
              {fmtMoney(order.total_cost)}
            </span>
          ) : (
            <span className="text-slate-400">—</span>
          )}
          {order.status === "shipped" ? (
            <button
              className="p-2 -m-1 rounded hover:bg-slate-100 text-slate-400"
              onClick={() => onEditCost(order)}
              aria-label="تعديل التكاليف"
            >
              <Pencil size={13} />
            </button>
          ) : null}
        </div>
      </div>

      {order.products.length ? (
        <div className="mt-2 text-xs text-slate-600">
          <span className="text-slate-400">المنتجات ({order.products.length}):</span>{" "}
          {order.products.slice(0, 3).map(productLabel).join(" | ")}
          {order.products.length > 3 ? " …" : ""}
        </div>
      ) : null}

      <div className="mt-3 pt-2 border-t border-slate-100 flex items-center gap-2">
        {order.status === "waiting" ? (
          <button className="btn-ghost !py-1.5 text-sm text-emerald-700" onClick={() => onShip(order)}>
            <PackageCheck size={14} /> تم الشحن
          </button>
        ) : (
          <span className="text-xs text-emerald-700 flex items-center gap-1">
            <CheckCircle2 size={12} /> {order.shipped_at ? fmtDate(order.shipped_at) : ""}
          </span>
        )}
        <div className="flex-1" />
        <button className="btn-ghost !py-1.5 !px-3 text-sm" onClick={() => onDetails(order)}>
          <ListTree size={14} /> التفاصيل
        </button>
        <button className="btn-ghost !py-2 !px-3 text-red-600" onClick={() => onDelete(order)} aria-label="حذف">
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

const hasCosts = (o: SupplierOrder) => o.shipment_cost !== null && o.shipment_cost !== undefined;

/** Everything recorded against one purchase order: its lines, and what it cost. */
function OrderDetailsModal({ order, onClose }: { order: SupplierOrder | null; onClose: () => void }) {
  return (
    <Modal open={order !== null} onClose={onClose} title="تفاصيل أمر الشراء" size="lg">
      {order ? (
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div>
              <div className="num font-bold text-lg text-slate-800" dir="ltr">{order.order_number}</div>
              <div className="text-sm text-slate-700">{order.supplier_name}</div>
              {order.supplier_company ? (
                <div className="text-xs text-slate-500">{order.supplier_company}</div>
              ) : null}
            </div>
            <StatusBadge status={order.status} />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
            <Field label="تاريخ الطلب" value={fmtDate(order.order_date)} />
            <Field label="تاريخ الشحن" value={fmtDate(order.shipping_date)} />
            <Field label="تم الشحن في" value={order.shipped_at ? fmtDate(order.shipped_at) : "—"} />
          </div>

          <div>
            <div className="font-bold text-sm mb-2">المنتجات ({order.products.length})</div>
            {order.products.length === 0 ? (
              <p className="text-sm text-slate-500">لم تُسجَّل منتجات على هذا الأمر.</p>
            ) : (
              <div className="overflow-x-auto scroll-thin">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-500 border-b border-slate-100">
                      <th className="py-2 text-right font-medium">الاسم</th>
                      <th className="py-2 text-right font-medium">رقم الطراز</th>
                      <th className="py-2 text-right font-medium">اللون</th>
                      <th className="py-2 text-right font-medium">رقم الطيف</th>
                    </tr>
                  </thead>
                  <tbody>
                    {order.products.map(p => (
                      <tr key={p.id} className="border-b border-slate-50 last:border-0">
                        <td className="py-2">{p.name || "—"}</td>
                        <td className="py-2 num" dir="ltr">{p.quality || "—"}</td>
                        <td className="py-2">{p.color || "—"}</td>
                        <td className="py-2 num" dir="ltr">{p.shade || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div>
            <div className="font-bold text-sm mb-2">التكاليف</div>
            {!hasCosts(order) ? (
              <p className="text-sm text-slate-500">لم تُسجَّل تكاليف لهذا الأمر.</p>
            ) : (
              <div className="rounded-xl border border-slate-200 divide-y divide-slate-100 text-sm">
                <CostRow label="تكلفة البضاعة" amount={order.shipment_cost ?? 0} />
                <CostRow
                  label="تكلفة الشحن"
                  amount={order.shipping_amount}
                  note={order.shipping_is_percent ? `${Number(order.shipping_value)}% من البضاعة` : undefined}
                />
                <CostRow
                  label="تكلفة الجمركة"
                  amount={order.customs_amount}
                  note={order.customs_is_percent ? `${Number(order.customs_value)}% من البضاعة` : undefined}
                />
                <div className="flex items-center justify-between px-3 py-2 bg-slate-50 rounded-b-xl">
                  <span className="font-bold text-slate-700">الإجمالي</span>
                  <span className="num font-bold text-slate-900" dir="ltr">{fmtTotal(order.total_cost)}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-2.5 py-1.5">
      <div className="text-slate-500">{label}</div>
      <div className="num font-semibold text-slate-800">{value}</div>
    </div>
  );
}

function CostRow({ label, amount, note }: { label: string; amount: string | number; note?: string }) {
  return (
    <div className="flex items-center justify-between px-3 py-2">
      <span className="text-slate-600">
        {label}
        {note ? <span className="text-xs text-slate-400 mr-1">({note})</span> : null}
      </span>
      <span className="num text-slate-800" dir="ltr">{fmtMoney(amount)}</span>
    </div>
  );
}
