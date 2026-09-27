"use client";
import { Fragment, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Customer, CustomerBalance, SalesOrder, InventoryItem } from "@/types";
import { Modal } from "@/components/Modal";
import { ItemPicker, itemLabel } from "@/components/ItemPicker";
import { useConfirm } from "@/components/ConfirmDialog";
import { fmtDate, fmtQty, fmtTotal, today } from "@/lib/format";
import {
  Plus, Trash2, Wallet, Users, ReceiptText, CheckCircle2, AlertTriangle, X,
  Lock, Unlock, FileText, ChevronDown, ChevronUp, ClipboardList, Pencil, Search,
} from "lucide-react";

type SoLine = { inventory_item_id: string; qty: string; unit_price: string; priceLocked: boolean };
const emptyLine: SoLine = { inventory_item_id: "", qty: "", unit_price: "", priceLocked: true };

/** Money, kept to cents so repeated splitting can't drift. */
const round2 = (n: number) => Math.round((Number(n) || 0) * 100) / 100;

const CUSTOMER_PAGE = 10;   // the rest are a click away
const ORDER_PAGE = 50;

export default function CreditorsPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [balances, setBalances] = useState<CustomerBalance[]>([]);
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [filter, setFilter] = useState<"all" | "unpaid" | "paid">("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [custQuery, setCustQuery] = useState("");
  const [custShown, setCustShown] = useState(CUSTOMER_PAGE);
  const [balShown, setBalShown] = useState(ORDER_PAGE);

  const [showCustModal, setShowCustModal] = useState(false);
  const [editingCust, setEditingCust] = useState<Customer | null>(null);
  const [cust, setCust] = useState({ name: "", phone: "", city: "", notes: "" });

  const [showSoModal, setShowSoModal] = useState(false);
  const [emptyStockWarn, setEmptyStockWarn] = useState(0);
  const [so, setSo] = useState({
    customer_id: "",
    order_date: today(),
    notes: "",
    items: [{ ...emptyLine }] as SoLine[],
    // what the customer should actually pay; blank means no discount
    finalTotal: "",
  });

  const [payFor, setPayFor] = useState<SalesOrder | null>(null);
  const [pay, setPay] = useState({ amount: "", method: "cash", paid_at: today() });
  // a handover bigger than the invoice it was entered on, waiting to be split
  const [split, setSplit] = useState<{
    customerId: string;
    customerName: string;
    total: number;
    paid_at: string;
    method: string;
    alloc: Record<string, number>;
  } | null>(null);
  const { ask, confirmUi } = useConfirm();

  async function load() {
    setErr(null);
    try {
      const [c, b, o, i] = await Promise.all([
        api.get<Customer[]>("/api/creditors/customers"),
        api.get<CustomerBalance[]>("/api/creditors/balances"),
        api.get<SalesOrder[]>("/api/creditors/sales-orders"),
        api.get<InventoryItem[]>("/api/storage/items"),
      ]);
      setCustomers(c); setBalances(b); setOrders(o); setItems(i);
    } catch (e: any) { setErr(e.message); }
  }
  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!emptyStockWarn) return;
    const t = setTimeout(() => setEmptyStockWarn(0), 5000);
    return () => clearTimeout(t);
  }, [emptyStockWarn]);

  const filteredBalances = useMemo(() => {
    if (filter === "unpaid") return balances.filter(b => Number(b.outstanding) > 0);
    if (filter === "paid") return balances.filter(b => Number(b.outstanding) <= 0);
    return balances;
  }, [balances, filter]);

  // the search runs over every customer, so a name beyond the cap is still findable
  const matchedCustomers = useMemo(() => {
    const terms = custQuery.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) return customers;
    return customers.filter(c => {
      const hay = [c.name, c.phone, c.city].filter(Boolean).join(" ").toLowerCase();
      return terms.every(t => hay.includes(t));
    });
  }, [customers, custQuery]);

  useEffect(() => { setCustShown(CUSTOMER_PAGE); }, [custQuery]);
  useEffect(() => { setBalShown(ORDER_PAGE); }, [filter]);

  const ordersByCustomer = useMemo(() => {
    const map: Record<string, SalesOrder[]> = {};
    for (const o of orders) (map[o.customer_id] ??= []).push(o);
    return map;
  }, [orders]);

  function openInvoice(orderId: string) {
    window.open(`/invoice/${orderId}`, "_blank");
  }

  /** Issue a كشف حساب for the year up to today, then open it for printing. */
  async function openStatement(customerId: string) {
    setBusy(true);
    try {
      const st = await api.post<{ id: string }>(`/api/creditors/customers/${customerId}/statements`);
      window.open(`/statement/${st.id}`, "_blank");
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  function openNewCustomer() {
    setEditingCust(null);
    setCust({ name: "", phone: "", city: "", notes: "" });
    setShowCustModal(true);
  }

  function openEditCustomer(c: Customer) {
    setEditingCust(c);
    setCust({ name: c.name, phone: c.phone ?? "", city: c.city ?? "", notes: c.notes ?? "" });
    setShowCustModal(true);
  }

  async function saveCustomer() {
    setBusy(true);
    setErr(null);
    try {
      if (editingCust) {
        await api.put(`/api/creditors/customers/${editingCust.id}`, cust);
      } else {
        await api.post("/api/creditors/customers", cust);
      }
      setCust({ name: "", phone: "", city: "", notes: "" });
      setEditingCust(null);
      setShowCustModal(false);
      load();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  async function deleteCustomer(c: Customer) {
    if (!(await ask(`حذف الزبون ${c.name}؟`))) return;
    setErr(null);
    try {
      await api.del(`/api/creditors/customers/${c.id}`);
      load();
    } catch (e: any) { setErr(e.message); }
  }

  async function saveSo() {
    setBusy(true);
    try {
      const payload = {
        customer_id: so.customer_id,
        order_date: so.order_date,
        notes: so.notes || undefined,
        items: so.items
          .filter(l => l.inventory_item_id && Number(l.qty) > 0)
          .map(l => ({
            inventory_item_id: l.inventory_item_id,
            qty: Number(l.qty),
            unit_price: Number(l.unit_price || 0),
          })),
        discount: soDiscount > 0 ? soDiscount : 0,
      };
      if (!payload.customer_id || !payload.items.length) {
        throw new Error("اختر زبون وأضف صنفًا واحدًا على الأقل");
      }
      const created = await api.post<SalesOrder>("/api/creditors/sales-orders", payload);
      setShowSoModal(false);
      setSo({ customer_id: "", order_date: today(), notes: "", items: [{ ...emptyLine }], finalTotal: "" });
      load();
      openInvoice(created.id);      // straight to the printable invoice
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  async function addPayment() {
    if (!payFor) return;
    const amount = round2(Number(pay.amount));
    const outstanding = round2(Number(payFor.outstanding));

    // More than this invoice owes: settle it, then ask where the rest goes
    // rather than letting the overflow sit on one bill.
    if (amount > outstanding) {
      setSplit({
        customerId: payFor.customer_id,
        customerName: payFor.customer_name ?? "",
        total: amount,
        paid_at: pay.paid_at,
        method: pay.method,
        alloc: { [payFor.id]: outstanding },
      });
      setPayFor(null);
      return;
    }

    setBusy(true);
    try {
      await api.post("/api/creditors/payments", {
        sales_order_id: payFor.id,
        paid_at: pay.paid_at,
        amount,
        method: pay.method,
      });
      setPayFor(null);
      setPay({ amount: "", method: "cash", paid_at: today() });
      load();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  /** Commit the split — one write, so the money can't land half-applied. */
  async function confirmSplit() {
    if (!split) return;
    setBusy(true);
    try {
      await api.post("/api/creditors/payments/batch", {
        paid_at: split.paid_at,
        method: split.method,
        allocations: Object.entries(split.alloc)
          .filter(([, amt]) => amt > 0)
          .map(([sales_order_id, amount]) => ({ sales_order_id, amount })),
      });
      setSplit(null);
      setPay({ amount: "", method: "cash", paid_at: today() });
      load();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  async function deleteSo(id: string) {
    if (!(await ask("حذف فاتورة البيع وإرجاع الكميات للمخزون؟"))) return;
    try {
      await api.del(`/api/creditors/sales-orders/${id}`);
      // the payment dialog would otherwise stay open on a deleted invoice
      setPayFor(p => (p?.id === id ? null : p));
      load();
    } catch (e: any) { setErr(e.message); }
  }

  const soItemsTotal = round2(so.items.reduce(
    (s, l) => s + Number(l.qty || 0) * Number(l.unit_price || 0), 0
  ));
  // The user types what they want charged; the discount is the gap.
  const soFinal = so.finalTotal.trim() === "" ? soItemsTotal : round2(Number(so.finalTotal));
  const soDiscount = round2(soItemsTotal - soFinal);
  const discountInvalid =
    so.finalTotal.trim() !== "" &&
    (!Number.isFinite(soFinal) || soFinal < 0 || soFinal > soItemsTotal);

  // ---- splitting one handover across a customer's open invoices ----
  const splitRows = split
    ? (ordersByCustomer[split.customerId] ?? [])
        .map(o => {
          const allocated = round2(split.alloc[o.id] ?? 0);
          return { order: o, allocated, room: round2(Number(o.outstanding) - allocated) };
        })
        .filter(r => r.room > 0 || r.allocated > 0)
        .sort((a, b) => a.order.order_number.localeCompare(b.order.order_number))
    : [];
  const splitAllocated = split
    ? round2(Object.values(split.alloc).reduce((s, v) => s + v, 0))
    : 0;
  const splitRemaining = split ? round2(split.total - splitAllocated) : 0;
  const splitRoomLeft = round2(splitRows.reduce((s, r) => s + r.room, 0));

  function allocate(orderId: string, amount: number) {
    setSplit(s => (s
      ? { ...s, alloc: { ...s.alloc, [orderId]: round2((s.alloc[orderId] ?? 0) + amount) } }
      : s));
  }

  function unallocate(orderId: string) {
    setSplit(s => {
      if (!s) return s;
      const { [orderId]: _dropped, ...rest } = s.alloc;
      return { ...s, alloc: rest };
    });
  }

  /** Lines asking for more than is in stock, summed per item so two lines of
   *  the same product can't each look fine and overdraw it together. */
  const shortages = (() => {
    const wanted = new Map<string, number>();
    for (const l of so.items) {
      const qty = Number(l.qty || 0);
      if (!l.inventory_item_id || !Number.isFinite(qty) || qty <= 0) continue;
      wanted.set(l.inventory_item_id, (wanted.get(l.inventory_item_id) ?? 0) + qty);
    }
    const out = new Map<string, { wanted: number; available: number; label: string; unit: string }>();
    for (const [id, qty] of wanted) {
      const item = items.find(i => i.id === id);
      if (!item) continue;
      const available = Number(item.qty_on_hand || 0);
      if (qty > available) {
        out.set(id, { wanted: qty, available, label: itemLabel(item), unit: item.unit });
      }
    }
    return out;
  })();

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-800 flex items-center gap-2">
            <Users size={22} className="text-brand" /> الزبائن والذمم
          </h1>
          <p className="text-sm text-slate-500">من دفع بالكامل، ومن ما زال عليه رصيد</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={openNewCustomer}><Plus size={16} /> زبون جديد</button>
          <button
            className="btn-primary"
            onClick={() => {
              if (items.length === 0) { setEmptyStockWarn(n => n + 1); return; }
              setEmptyStockWarn(0);
              setShowSoModal(true);
            }}
            disabled={customers.length === 0}
          >
            <ReceiptText size={16} /> فاتورة بيع جديدة
          </button>
        </div>
      </header>

      {err ? <div className="card text-red-700 text-sm">{err}</div> : null}

      {emptyStockWarn ? (
        <div className="card border-r-4 border-amber-400 flex items-center gap-2 text-amber-800 text-sm">
          <AlertTriangle size={16} className="shrink-0" />
          <span className="flex-1">المخزن فارغ, لا يوجد مخزون للبيع</span>
          <button onClick={() => setEmptyStockWarn(0)} className="p-1 rounded-lg hover:bg-amber-50" aria-label="إغلاق">
            <X size={16} />
          </button>
        </div>
      ) : null}

      {/* Every customer, including ones with no invoices yet — the balances
          table below only lists those who have been billed. */}
      <div className="card">
        <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
          <div className="font-bold">الزبائن ({customers.length})</div>
          <div className="relative flex-1 min-w-[180px] max-w-xs">
            <Search size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              className="input !py-1.5 pr-8 text-sm"
              placeholder="ابحث بالاسم أو الهاتف أو المدينة..."
              value={custQuery}
              onChange={e => setCustQuery(e.target.value)}
            />
          </div>
        </div>

        {matchedCustomers.length === 0 ? (
          <p className="text-sm text-slate-500">
            {customers.length === 0 ? "لا يوجد زبائن بعد." : "لا توجد نتائج."}
          </p>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2">
              {matchedCustomers.slice(0, custShown).map(c => {
                const count = (ordersByCustomer[c.id] ?? []).length;
                return (
                  <div
                    key={c.id}
                    className="rounded-lg border border-slate-200 px-2.5 py-2 flex items-center gap-2"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-sm text-slate-800 truncate">{c.name}</div>
                      <div className="text-[11px] text-slate-500 truncate">
                        <span className="num" dir="ltr">{c.phone || "—"}</span>
                        {c.city ? ` · ${c.city}` : ""}
                        {count ? ` · ${count} فاتورة` : ""}
                      </div>
                    </div>
                    <div className="flex items-center shrink-0">
                      <button
                        className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500"
                        onClick={() => openEditCustomer(c)}
                        aria-label="تعديل"
                      >
                        <Pencil size={13} />
                      </button>
                      <button
                        className="p-1.5 rounded-lg hover:bg-red-50 text-red-600 disabled:opacity-30 disabled:hover:bg-transparent"
                        onClick={() => deleteCustomer(c)}
                        disabled={count > 0}
                        title={count > 0 ? "لا يمكن الحذف — لديه فواتير" : "حذف"}
                        aria-label="حذف"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
            {matchedCustomers.length > custShown ? (
              <button
                className="btn-ghost !py-1.5 mt-3 text-sm"
                onClick={() => setCustShown(n => n + CUSTOMER_PAGE)}
              >
                <ChevronDown size={14} /> عرض المزيد ({matchedCustomers.length - custShown})
              </button>
            ) : null}
          </>
        )}
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div className="font-bold">أرصدة الزبائن</div>
          <div className="flex gap-1 text-xs">
            {(["all", "unpaid", "paid"] as const).map(k => (
              <button key={k} onClick={() => setFilter(k)}
                className={`px-3 py-2 rounded-lg ${filter === k ? "bg-brand text-white" : "bg-slate-100 text-slate-700"}`}>
                {k === "all" ? "الكل" : k === "unpaid" ? "لم يدفعوا" : "دفعوا بالكامل"}
              </button>
            ))}
          </div>
        </div>

        {/* Mobile: cards — the money columns fall off the right of a phone
            screen when this is a table. */}
        <div className="md:hidden space-y-2">
          {filteredBalances.slice(0, balShown).map(b => {
            const custOrders = ordersByCustomer[b.customer_id] ?? [];
            const isOpen = expanded === b.customer_id;
            return (
              <div
                key={b.customer_id}
                className={`rounded-xl border p-3 ${
                  b.fully_paid ? "border-emerald-200 bg-emerald-50/60" : "border-amber-200 bg-amber-50/50"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-bold text-slate-800">{b.customer_name}</div>
                    <div className="text-xs text-slate-500 num" dir="ltr">{b.phone || "—"}</div>
                  </div>
                  {b.fully_paid ? (
                    <span className="badge-green inline-flex items-center gap-1">
                      <CheckCircle2 size={12} /> مسدّد
                    </span>
                  ) : (
                    <span className="num font-extrabold text-amber-800">{fmtTotal(b.outstanding)}</span>
                  )}
                </div>

                <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                  <div><div className="text-slate-400">مفوتر</div><div className="num font-semibold">{fmtTotal(b.invoiced)}</div></div>
                  <div><div className="text-slate-400">مدفوع</div><div className="num font-semibold">{fmtTotal(b.paid)}</div></div>
                  <div><div className="text-slate-400">آخر فاتورة</div><div className="num">{b.last_order_date ? fmtDate(b.last_order_date) : "—"}</div></div>
                </div>

                <button
                  className="btn-ghost !py-2 !px-3 text-xs mt-2 ml-2"
                  disabled={busy}
                  onClick={() => openStatement(b.customer_id)}
                >
                  <ClipboardList size={13} /> كشف حساب
                </button>

                {custOrders.length ? (
                  <>
                    <button
                      className="btn-ghost !py-2 !px-3 text-xs mt-2"
                      onClick={() => setExpanded(isOpen ? null : b.customer_id)}
                    >
                      <FileText size={13} /> الفواتير ({custOrders.length})
                      {isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    </button>
                    {isOpen ? (
                      <div className="mt-2 space-y-2">
                        {custOrders.map(o => (
                          <div key={o.id} className="rounded-lg bg-white border border-slate-100 p-2">
                            <div className="flex items-center justify-between gap-2">
                              <span className="num font-semibold text-sm" dir="ltr">{o.order_number}</span>
                              <span className="text-xs text-slate-500">{fmtDate(o.order_date)}</span>
                            </div>
                            <div className="flex items-center gap-3 text-xs mt-1">
                              <span>الإجمالي <span className="num font-semibold">{fmtTotal(o.subtotal)}</span></span>
                              <span>المتبقي{" "}
                                <span className={`num font-semibold ${Number(o.outstanding) > 0 ? "text-amber-800" : "text-emerald-700"}`}>
                                  {fmtTotal(o.outstanding)}
                                </span>
                              </span>
                            </div>
                            <div className="flex items-center gap-1 mt-2">
                              <button className="btn-ghost !py-2 !px-3 text-xs" onClick={() => openInvoice(o.id)}>
                                <FileText size={13} /> فاتورة PDF
                              </button>
                              {Number(o.outstanding) > 0 ? (
                                <button className="btn-ghost !py-2 !px-3 text-xs" onClick={() => setPayFor(o)}>
                                  <Wallet size={13} /> دفعة
                                </button>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-emerald-700 text-xs px-2">
                                  <CheckCircle2 size={13} /> مكتملة
                                </span>
                              )}
                              <div className="flex-1" />
                              <button className="btn-ghost !py-2 !px-3 text-red-600" onClick={() => deleteSo(o.id)} aria-label="حذف">
                                <Trash2 size={13} />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>
            );
          })}
          {filteredBalances.length === 0 ? (
            <p className="py-6 text-center text-slate-500 text-sm">لا يوجد أرصدة لعرضها.</p>
          ) : null}
        </div>

        <div className="hidden md:block overflow-x-auto scroll-thin">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-right text-slate-500">
                <Th>الزبون</Th><Th>الهاتف</Th><Th>آخر فاتورة</Th>
                <Th>مفوتر</Th><Th>مدفوع</Th><Th>الرصيد</Th>
              </tr>
            </thead>
            <tbody>
              {filteredBalances.slice(0, balShown).map(b => {
                const custOrders = ordersByCustomer[b.customer_id] ?? [];
                const isOpen = expanded === b.customer_id;
                // dim yellow = still owes, green = settled
                const tone = b.fully_paid
                  ? "bg-emerald-50/70 hover:bg-emerald-50"
                  : "bg-amber-50/60 hover:bg-amber-50";
                return (
                  <Fragment key={b.customer_id}>
                    <tr className={`border-t border-slate-100 ${tone}`}>
                      <Td className="font-semibold">
                        <div className="flex items-center gap-2">
                          <span>{b.customer_name}</span>
                          {custOrders.length ? (
                            <button
                              className="btn-ghost !py-1 !px-2 text-xs"
                              onClick={() => setExpanded(isOpen ? null : b.customer_id)}
                              aria-label="الفواتير"
                            >
                              <FileText size={13} /> {custOrders.length}
                              {isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                            </button>
                          ) : null}
                          <button
                            className="btn-ghost !py-1 !px-2 text-xs"
                            disabled={busy}
                            title="كشف حساب لآخر سنة"
                            onClick={() => openStatement(b.customer_id)}
                          >
                            <ClipboardList size={13} /> كشف حساب
                          </button>
                        </div>
                      </Td>
                      <Td dir="ltr" className="num">{b.phone || "—"}</Td>
                      <Td className="num">{b.last_order_date ? fmtDate(b.last_order_date) : "—"}</Td>
                      <Td className="num">{fmtTotal(b.invoiced)}</Td>
                      <Td className="num">{fmtTotal(b.paid)}</Td>
                      <Td className="num font-bold">
                        {b.fully_paid ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700">
                            <CheckCircle2 size={13} /> {fmtTotal(0)}
                          </span>
                        ) : (
                          <span className="text-amber-800">{fmtTotal(b.outstanding)}</span>
                        )}
                      </Td>
                    </tr>

                    {isOpen ? (
                      <tr className="border-t border-slate-100">
                        <td colSpan={6} className="p-0">
                          <div className="bg-slate-50 px-4 py-3">
                            <div className="text-xs font-semibold text-slate-500 mb-2">فواتير {b.customer_name}</div>
                            <div className="space-y-1.5">
                              {custOrders.map(o => (
                                <div key={o.id} className="flex items-center gap-2 flex-wrap rounded-lg bg-white border border-slate-100 px-3 py-2">
                                  <span className="num font-semibold" dir="ltr">{o.order_number}</span>
                                  <span className="text-xs text-slate-500">{fmtDate(o.order_date)}</span>
                                  <span className="text-xs">الإجمالي <span className="num font-semibold">{fmtTotal(o.subtotal)}</span></span>
                                  <span className="text-xs">المتبقي{" "}
                                    <span className={`num font-semibold ${Number(o.outstanding) > 0 ? "text-amber-800" : "text-emerald-700"}`}>
                                      {fmtTotal(o.outstanding)}
                                    </span>
                                  </span>
                                  <div className="flex-1" />
                                  <button className="btn-ghost !py-1 !px-2 text-xs" onClick={() => openInvoice(o.id)}>
                                    <FileText size={13} /> فاتورة PDF
                                  </button>
                                  {Number(o.outstanding) > 0 ? (
                                    <button className="btn-ghost !py-1 !px-2 text-xs" onClick={() => setPayFor(o)}>
                                      <Wallet size={13} /> دفعة
                                    </button>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 text-emerald-700 text-xs">
                                      <CheckCircle2 size={13} /> مكتملة
                                    </span>
                                  )}
                                  <button className="btn-ghost !py-1 !px-2 text-red-600" onClick={() => deleteSo(o.id)} aria-label="حذف">
                                    <Trash2 size={13} />
                                  </button>
                                </div>
                              ))}
                            </div>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
              {filteredBalances.length === 0 ? (
                <tr><td colSpan={6} className="py-6 text-center text-slate-500 text-sm">لا يوجد أرصدة لعرضها.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>

        {filteredBalances.length > balShown ? (
          <button
            className="btn-ghost !py-2 mt-3 text-sm"
            onClick={() => setBalShown(n => n + ORDER_PAGE)}
          >
            <ChevronDown size={14} /> عرض المزيد ({filteredBalances.length - balShown})
          </button>
        ) : null}
      </div>

      {/* New customer */}
      <Modal
        open={showCustModal}
        onClose={() => { setShowCustModal(false); setEditingCust(null); }}
        title={editingCust ? "تعديل الزبون" : "زبون جديد"}
      >
        <div className="space-y-3">
          <div><label className="label">الاسم *</label><input className="input" value={cust.name} onChange={e => setCust({ ...cust, name: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">الهاتف</label><input dir="ltr" className="input" value={cust.phone} onChange={e => setCust({ ...cust, phone: e.target.value })} /></div>
            <div><label className="label">المدينة</label><input className="input" value={cust.city} onChange={e => setCust({ ...cust, city: e.target.value })} /></div>
          </div>
          <div><label className="label">ملاحظات</label><textarea className="textarea" value={cust.notes} onChange={e => setCust({ ...cust, notes: e.target.value })} /></div>
          <button className="btn-primary w-full" disabled={busy || !cust.name} onClick={saveCustomer}>حفظ</button>
        </div>
      </Modal>

      {/* New sales order */}
      <Modal open={showSoModal} onClose={() => setShowSoModal(false)} title="فاتورة بيع جديدة" size="xl">
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">الزبون *</label>
              <select className="select" value={so.customer_id} onChange={e => setSo({ ...so, customer_id: e.target.value })}>
                <option value="">— اختر —</option>
                {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label">التاريخ</label>
              <input type="date" className="input" value={so.order_date} onChange={e => setSo({ ...so, order_date: e.target.value })} />
            </div>
          </div>

          <div className="space-y-3">
            {so.items.map((l, idx) => {
              const item = items.find(i => i.id === l.inventory_item_id);
              const lineTotal = Number(l.qty || 0) * Number(l.unit_price || 0);
              const short = shortages.get(l.inventory_item_id);
              return (
                <div key={idx} className="rounded-xl border border-slate-200 p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-500">صنف {idx + 1}</span>
                    {so.items.length > 1 ? (
                      <button className="p-1 text-red-600 hover:bg-red-50 rounded" onClick={() => removeSoLine(idx)}>
                        <Trash2 size={14} />
                      </button>
                    ) : null}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <div className="sm:col-span-2">
                      <label className="label">الصنف *</label>
                      <ItemPicker
                        items={items}
                        value={l.inventory_item_id}
                        onChange={id => pickItem(idx, id)}
                      />
                      {item ? (
                        <div className="text-xs text-slate-500 mt-1">
                          المتوفر: <span className="num">{Number(item.qty_on_hand).toLocaleString()} {item.unit}</span>
                        </div>
                      ) : null}
                    </div>
                    <div>
                      <label className="label">الكمية</label>
                      <input
                        dir="ltr"
                        className={`input num ${short ? "border-red-300 focus:border-red-400 focus:ring-red-100" : ""}`}
                        value={l.qty}
                        onChange={e => updateSoLine(idx, { qty: e.target.value })}
                      />
                      {short ? (
                        <p className="text-[11px] text-red-600 mt-1 leading-tight">
                          المتوفر <span className="num">{fmtQty(short.available)} {short.unit}</span> فقط
                        </p>
                      ) : null}
                    </div>
                    <div>
                      <label className="label">سعر البيع</label>
                      <div className="flex gap-1">
                        <input
                          dir="ltr"
                          className={`input num ${l.priceLocked ? "bg-slate-50 text-slate-500" : ""}`}
                          value={l.unit_price}
                          disabled={l.priceLocked}
                          onChange={e => updateSoLine(idx, { unit_price: e.target.value })}
                        />
                        <button
                          type="button"
                          className={`btn-ghost !px-2 ${l.priceLocked ? "text-slate-400" : "text-brand"}`}
                          onClick={() => updateSoLine(idx, { priceLocked: !l.priceLocked })}
                          aria-label={l.priceLocked ? "فتح السعر للتعديل" : "قفل السعر"}
                          title={l.priceLocked ? "فتح السعر للتعديل" : "قفل السعر"}
                        >
                          {l.priceLocked ? <Lock size={14} /> : <Unlock size={14} />}
                        </button>
                      </div>
                    </div>
                  </div>

                </div>
              );
            })}
          </div>

          <button className="btn-ghost !py-2 text-sm"
                  onClick={() => setSo({ ...so, items: [...so.items, { ...emptyLine }] })}>
            <Plus size={14} /> إضافة صنف
          </button>

          <div className="rounded-xl bg-slate-50 p-3 text-sm space-y-2">
            <div className="flex justify-between">
              <span className="text-slate-600">إجمالي الأصناف</span>
              <span className="num font-semibold text-slate-800">{fmtTotal(soItemsTotal)}</span>
            </div>

            <div className="flex items-center justify-between gap-3">
              <label className="text-slate-600 shrink-0">الإجمالي بعد الخصم</label>
              <input
                dir="ltr"
                className={`input num !py-1.5 max-w-[10rem] ${discountInvalid ? "border-red-300" : ""}`}
                inputMode="decimal"
                placeholder={String(soItemsTotal)}
                value={so.finalTotal}
                onChange={e => setSo({ ...so, finalTotal: e.target.value })}
              />
            </div>
            {discountInvalid ? (
              <p className="text-xs text-red-600">
                أدخل مبلغًا بين 0 و <span className="num">{fmtTotal(soItemsTotal)}</span>.
              </p>
            ) : soDiscount > 0 ? (
              <div className="flex justify-between text-emerald-700">
                <span>الخصم</span>
                <span className="num font-semibold">−{fmtTotal(soDiscount)}</span>
              </div>
            ) : (
              <p className="text-[11px] text-slate-400">اتركه فارغًا إن لم يكن هناك خصم</p>
            )}

            <div className="flex justify-between text-base pt-2 border-t border-slate-200">
              <span className="font-bold">المطلوب</span>
              <span className="num font-extrabold text-slate-900">
                {fmtTotal(discountInvalid ? soItemsTotal : soFinal)}
              </span>
            </div>
          </div>

          <div><label className="label">ملاحظات</label><textarea className="textarea" value={so.notes} onChange={e => setSo({ ...so, notes: e.target.value })} /></div>

          {shortages.size ? (
            <div className="rounded-xl border-r-4 border-red-400 bg-red-50 p-3 text-sm text-red-800 space-y-1">
              <div className="flex items-center gap-2 font-bold">
                <AlertTriangle size={16} className="shrink-0" /> الكمية غير كافية في المخزون
              </div>
              {[...shortages.values()].map(s => (
                <div key={s.label} className="text-xs">
                  «{s.label}» — المطلوب <span className="num">{fmtQty(s.wanted)}</span>{" "}
                  والمتوفر <span className="num">{fmtQty(s.available)} {s.unit}</span> فقط
                </div>
              ))}
            </div>
          ) : null}

          <button
            className="btn-primary w-full disabled:opacity-50"
            onClick={saveSo}
            disabled={busy || shortages.size > 0 || discountInvalid}
          >
            حفظ الفاتورة
          </button>
        </div>
      </Modal>

      {/* Payment */}
      <Modal open={!!payFor} onClose={() => setPayFor(null)} title={`تسجيل دفعة على ${payFor?.order_number ?? ""}`}>
        {payFor ? (
          <div className="space-y-3">
            <div className="text-sm text-slate-600">
              الزبون: <b>{payFor.customer_name}</b> · المتبقي: <span className="num font-bold">{fmtTotal(payFor.outstanding)}</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">المبلغ (USD)</label>
                <input dir="ltr" className="input num" value={pay.amount} onChange={e => setPay({ ...pay, amount: e.target.value })} />
              </div>
              <div>
                <label className="label">الطريقة</label>
                <select className="select" value={pay.method} onChange={e => setPay({ ...pay, method: e.target.value })}>
                  <option value="cash">نقدًا</option>
                  <option value="bank">حوالة بنكية</option>
                  <option value="remittance">حوالة</option>
                  <option value="other">أخرى</option>
                </select>
              </div>
              <div className="col-span-2">
                <label className="label">التاريخ</label>
                <input type="date" className="input" value={pay.paid_at} onChange={e => setPay({ ...pay, paid_at: e.target.value })} />
              </div>
            </div>
            <button className="btn-primary w-full" onClick={addPayment} disabled={busy || !pay.amount}>تسجيل الدفعة</button>
          </div>
        ) : null}
      </Modal>

      {/* Handover bigger than the invoice it was entered on */}
      <Modal
        open={split !== null}
        onClose={() => setSplit(null)}
        title="توزيع المبلغ على الفواتير"
        size="lg"
      >
        {split ? (
          <div className="space-y-3">
            <div className="text-sm text-slate-600">
              الزبون: <b>{split.customerName}</b>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl bg-slate-50 px-2 py-2">
                <div className="text-[11px] text-slate-500">المبلغ المستلم</div>
                <div className="num font-bold text-slate-900">{fmtTotal(split.total)}</div>
              </div>
              <div className="rounded-xl bg-slate-50 px-2 py-2">
                <div className="text-[11px] text-slate-500">تم توزيعه</div>
                <div className="num font-bold text-emerald-700">{fmtTotal(splitAllocated)}</div>
              </div>
              <div className={`rounded-xl px-2 py-2 ${splitRemaining > 0 ? "bg-amber-50" : "bg-slate-50"}`}>
                <div className="text-[11px] text-slate-500">المتبقي</div>
                <div className={`num font-bold ${splitRemaining > 0 ? "text-amber-800" : "text-slate-500"}`}>
                  {fmtTotal(splitRemaining)}
                </div>
              </div>
            </div>

            {splitRemaining > 0 ? (
              <p className="text-sm text-slate-700">
                بقي <span className="num font-bold">{fmtTotal(splitRemaining)}</span> — أين تريد إضافته؟
              </p>
            ) : null}

            <div className="space-y-2">
              {splitRows.map(({ order, allocated, room }) => {
                const addable = round2(Math.min(splitRemaining, room));
                return (
                  <div
                    key={order.id}
                    className={`rounded-xl border p-3 ${allocated > 0 ? "border-emerald-200 bg-emerald-50/50" : "border-slate-200"}`}
                  >
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <div className="min-w-0">
                        <div className="num font-semibold text-sm" dir="ltr">{order.order_number}</div>
                        <div className="text-xs text-slate-500">
                          {fmtDate(order.order_date)} · المتبقي{" "}
                          <span className="num">{fmtTotal(order.outstanding)}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {allocated > 0 ? (
                          <>
                            <span className="num text-sm font-bold text-emerald-700">
                              +{fmtTotal(allocated)}
                            </span>
                            <button
                              className="btn-ghost !py-1.5 !px-2 text-red-600"
                              onClick={() => unallocate(order.id)}
                              aria-label="إلغاء"
                            >
                              <X size={14} />
                            </button>
                          </>
                        ) : null}
                        {addable > 0 ? (
                          <button
                            className="btn-ghost !py-1.5 !px-3 text-sm"
                            onClick={() => allocate(order.id, addable)}
                          >
                            <Plus size={14} /> إضافة {fmtTotal(addable)}
                          </button>
                        ) : null}
                      </div>
                    </div>
                    {room === 0 && allocated > 0 ? (
                      <div className="mt-1 text-[11px] text-emerald-700 flex items-center gap-1">
                        <CheckCircle2 size={11} /> ستُغلق بالكامل
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>

            {splitRemaining > 0 && splitRoomLeft === 0 ? (
              <div className="rounded-xl border-r-4 border-amber-400 bg-amber-50 p-3 text-sm text-amber-900 flex items-start gap-2">
                <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                <span>
                  كل الفواتير مسدّدة. يجب إعادة{" "}
                  <span className="num font-bold">{fmtTotal(splitRemaining)}</span> للزبون.
                </span>
              </div>
            ) : null}

            <div className="flex gap-2">
              <button
                className="btn-primary flex-1 disabled:opacity-50"
                onClick={confirmSplit}
                disabled={busy || splitAllocated <= 0}
              >
                تسجيل {fmtTotal(splitAllocated)}
              </button>
              <button className="btn-ghost" disabled={busy} onClick={() => setSplit(null)}>
                إلغاء
              </button>
            </div>
          </div>
        ) : null}
      </Modal>

      {confirmUi}
    </div>
  );

  /** Selecting a product seeds the price from what the warehouse stores. */
  function pickItem(idx: number, id: string) {
    const item = items.find(i => i.id === id);
    setSo(prev => ({
      ...prev,
      items: prev.items.map((it, i) =>
        i === idx
          ? {
              ...it,
              inventory_item_id: id,
              // the price it last sold for, not what it cost us
              unit_price: it.priceLocked
                ? (item ? String(Number(item.selling_price)) : "")
                : it.unit_price,
            }
          : it
      ),
    }));
  }

  function updateSoLine(idx: number, patch: Partial<SoLine>) {
    setSo(prev => ({
      ...prev,
      items: prev.items.map((it, i) => {
        if (i !== idx) return it;
        const next = { ...it, ...patch };
        // re-locking snaps the price back to the stored one
        if (patch.priceLocked === true) {
          const item = items.find(x => x.id === next.inventory_item_id);
          if (item) next.unit_price = String(Number(item.selling_price));
        }
        return next;
      }),
    }));
  }

  function removeSoLine(idx: number) {
    setSo(prev => ({ ...prev, items: prev.items.length === 1 ? prev.items : prev.items.filter((_, i) => i !== idx) }));
  }
}

function Th({ children }: { children?: React.ReactNode }) {
  return <th className="text-right font-medium px-3 py-2 whitespace-nowrap">{children}</th>;
}
function Td({ children, className = "", dir }: { children: React.ReactNode; className?: string; dir?: string }) {
  return <td dir={dir} className={`px-3 py-2 whitespace-nowrap ${className}`}>{children}</td>;
}
