"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { fmtDate, fmtMoney, fmtTotal, fmtQty } from "@/lib/format";
import { Printer, SlidersHorizontal } from "lucide-react";

type InvoiceItem = {
  reference?: string | null;
  quality?: string | null;
  shade?: string | null;
  color?: string | null;
  name?: string | null;
  unit?: string | null;
  qty: string;
  unit_price: string;
  line_total: string;
};

/** The optional columns, in print order. السعر is not here — it never comes off. */
const COLUMNS = [
  {
    key: "name", label: "الاسم",
    th: "px-2 py-2 text-right", td: "px-2 py-2 text-xs",
    cell: (it: InvoiceItem) => it.name || "—",
  },
  {
    key: "reference", label: "الرقم التعريفي",
    th: "px-1 py-2 text-center w-20", td: "px-1 py-2 text-center num text-xs", dir: "ltr",
    cell: (it: InvoiceItem) => it.reference || "—",
  },
  {
    key: "color", label: "اللون",
    th: "px-1 py-2 text-center w-14", td: "px-1 py-2 text-center text-xs",
    cell: (it: InvoiceItem) => it.color || "—",
  },
  {
    key: "shade", label: "رقم الطيف",
    th: "px-1 py-2 text-center w-14", td: "px-1 py-2 text-center num text-xs", dir: "ltr",
    cell: (it: InvoiceItem) => it.shade || "—",
  },
  {
    key: "quality", label: "رقم الطراز",
    th: "px-1 py-2 text-center w-20", td: "px-1 py-2 text-center num text-xs", dir: "ltr",
    cell: (it: InvoiceItem) => it.quality || "—",
  },
  {
    key: "qty", label: "الكمية",
    th: "px-1 py-2 text-center w-16", td: "px-1 py-2 text-center num text-xs whitespace-nowrap", dir: "ltr",
    cell: (it: InvoiceItem) => `${fmtQty(it.qty)} ${it.unit ?? ""}`,
  },
  {
    key: "unit_price", label: "سعر الوحدة",
    th: "px-1 py-2 text-center w-16", td: "px-1 py-2 text-center num text-xs", dir: "ltr",
    cell: (it: InvoiceItem) => fmtMoney(it.unit_price),
  },
] as const;

type ColKey = (typeof COLUMNS)[number]["key"];

/** Hidden rather than visible, so a column added later shows up by default. */
const HIDDEN_KEY = "sezer.invoice.hiddenColumns";

function readHidden(): Set<ColKey> {
  try {
    const raw = localStorage.getItem(HIDDEN_KEY);
    return new Set(raw ? (JSON.parse(raw) as ColKey[]) : []);
  } catch {
    return new Set();
  }
}

type Invoice = {
  order_number: string;
  order_date: string;
  issued_at: string;
  customer_name: string;
  customer_phone?: string | null;
  customer_city?: string | null;
  items: InvoiceItem[];
  items_total: string;
  discount: string;
  subtotal: string;
};

export default function InvoicePage() {
  const params = useParams<{ id: string }>();
  const [inv, setInv] = useState<Invoice | null>(null);
  const [err, setErr] = useState<string | null>(null);
  // read after mount — the server render has no localStorage to match against
  const [hidden, setHidden] = useState<Set<ColKey>>(new Set());

  useEffect(() => {
    api.get<Invoice>(`/api/creditors/sales-orders/${params.id}/invoice`)
      .then(setInv)
      .catch(e => setErr(e.message));
  }, [params.id]);

  useEffect(() => {
    setHidden(readHidden());
    // another tab changing the choice updates this invoice too
    const onStorage = (e: StorageEvent) => {
      if (e.key === HIDDEN_KEY) setHidden(readHidden());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  function toggleColumn(key: ColKey) {
    setHidden(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      try { localStorage.setItem(HIDDEN_KEY, JSON.stringify([...next])); } catch {}
      return next;
    });
  }

  useEffect(() => {
    if (!inv) return;
    const t = setTimeout(() => window.print(), 400);
    return () => clearTimeout(t);
  }, [inv]);

  if (err) return <div className="p-8 text-red-700">{err}</div>;
  if (!inv) return <div className="p-8 text-slate-500">جارٍ التحميل...</div>;

  // Quantities total per unit — metres and pieces can't be added together.
  const qtyByUnit = inv.items.reduce<Record<string, number>>((acc, it) => {
    const unit = it.unit || "";
    acc[unit] = (acc[unit] ?? 0) + Number(it.qty || 0);
    return acc;
  }, {});

  const hasDiscount = Number(inv.discount) > 0;
  const cols = COLUMNS.filter(c => !hidden.has(c.key));
  // the footer label runs up to the quantity total; whatever sits after it is blank
  const qtyIdx = cols.findIndex(c => c.key === "qty");
  const leading = qtyIdx === -1 ? cols.length : qtyIdx;
  const trailing = qtyIdx === -1 ? 0 : cols.length - qtyIdx - 1;

  return (
    <div className="invoice-root bg-white text-slate-900 min-h-screen">
      <style jsx global>{`
        @page { size: A4; margin: 14mm; }
        @media print {
          .no-print { display: none !important; }
          .invoice-root { padding: 0 !important; }
          /* keep the watermark when printing — browsers drop backgrounds by default */
          * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        }
        .wm-layer {
          position: absolute;
          inset: 0;
          overflow: hidden;
          pointer-events: none;
          z-index: 0;
        }
        .wm-text {
          position: absolute;
          font-weight: 900;
          letter-spacing: 0.08em;
          color: #0f766e;
          opacity: 0.07;
          white-space: nowrap;
          transform: rotate(-45deg);
          transform-origin: center;
        }
      `}</style>

      <div className="no-print sticky top-0 z-20 bg-slate-100 border-b border-slate-200 px-4 py-2">
        <div className="flex justify-between items-center gap-2 flex-wrap">
          <span className="text-sm text-slate-600">استخدم «حفظ كـ PDF» في نافذة الطباعة</span>
          <button className="btn-primary !py-1.5" onClick={() => window.print()}>
            <Printer size={14} /> طباعة
          </button>
        </div>
        <div className="mt-2 pt-2 border-t border-slate-200 flex items-center gap-x-4 gap-y-1.5 flex-wrap">
          <span className="text-xs font-semibold text-slate-500 flex items-center gap-1">
            <SlidersHorizontal size={13} /> الأعمدة
          </span>
          {COLUMNS.map(c => (
            <label key={c.key} className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer select-none">
              <input
                type="checkbox"
                className="accent-brand w-3.5 h-3.5"
                checked={!hidden.has(c.key)}
                onChange={() => toggleColumn(c.key)}
              />
              {c.label}
            </label>
          ))}
          <span className="text-xs text-slate-400">· عمود السعر ثابت دائمًا</span>
        </div>
      </div>

      <div className="relative max-w-[820px] mx-auto p-4 sm:p-8 print:p-8 flex flex-col min-h-screen">
        {/* Watermark: oversized, rotated, bleeding past the edges on purpose */}
        <div className="wm-layer" aria-hidden="true">
          <div className="wm-text" style={{ top: "6%", left: "-14%", fontSize: "104px" }}>SEZER</div>
          <div className="wm-text" style={{ top: "34%", left: "26%", fontSize: "132px" }}>SEZER</div>
          <div className="wm-text" style={{ top: "66%", left: "-8%", fontSize: "112px" }}>SEZER</div>
          <div className="wm-text" style={{ top: "88%", left: "44%", fontSize: "96px" }}>SEZER</div>
        </div>

        <div className="relative flex-1" style={{ zIndex: 1 }}>
          {/* ── Top: brand + who this invoice is for ───────────────── */}
          {/* one right-aligned block — nothing sits on the left */}
          <div className="text-right border-b-2 border-slate-800 pb-4">
            <div className="text-2xl font-black text-brand leading-none">SEZER</div>
            <div className="text-sm font-bold text-slate-800 mt-1">فاتورة مبيعات</div>

            <div className="mt-3 text-xs text-slate-600">
              <div className="text-[11px] text-slate-400">الزبون</div>
              <div className="text-base font-bold text-slate-900">{inv.customer_name}</div>
              {inv.customer_phone ? (
                <div className="num inline-block" dir="ltr">{inv.customer_phone}</div>
              ) : null}
              {inv.customer_city ? <div>{inv.customer_city}</div> : null}
              <div className="mt-1.5">
                رقم الفاتورة:{" "}
                <span className="num font-semibold inline-block whitespace-nowrap" dir="ltr">
                  {inv.order_number}
                </span>
              </div>
              <div>التاريخ: <span className="num">{fmtDate(inv.order_date)}</span></div>
            </div>
          </div>

          {/* ── Body: columns side by side. The total stands alone on the
                 right; the item columns run to its left. On a phone it
                 stacks, so the table keeps its width instead of crushing. ── */}
          <div className="mt-6 flex flex-col sm:flex-row items-stretch sm:items-start gap-4 print:flex-row">
            <div className="w-full sm:w-28 shrink-0 print:w-28">
              <div className="bg-slate-100/90 text-[11px] font-medium px-2 py-2 text-center">
                الإجمالي
              </div>
              <div className="border-b border-slate-100 px-2 py-3 text-center">
                {hasDiscount ? (
                  <div className="mb-1">
                    <div className="num text-xs text-slate-400 line-through" dir="ltr">
                      {fmtTotal(inv.items_total)}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      خصم <span className="num">{fmtTotal(inv.discount)}</span>
                    </div>
                  </div>
                ) : null}
                <span className="num text-lg font-black" dir="ltr">{fmtTotal(inv.subtotal)}</span>
              </div>
            </div>

            <div className="flex-1 min-w-0 overflow-x-auto scroll-thin">
              <table className="w-full min-w-[520px] text-sm table-fixed print:min-w-0">
                <thead>
                  {/* الاسم takes the slack so Arabic names don't wrap */}
                  <tr className="bg-slate-100/90 text-[11px]">
                    {cols.map(c => <th key={c.key} className={c.th}>{c.label}</th>)}
                    <th className="px-1 py-2 text-center w-20">السعر</th>
                  </tr>
                </thead>
                <tbody>
                  {inv.items.map((it, idx) => (
                    <tr key={idx} className="border-b border-slate-100">
                      {cols.map(c => (
                        <td key={c.key} className={c.td} dir={"dir" in c ? c.dir : undefined}>
                          {c.cell(it)}
                        </td>
                      ))}
                      <td className="px-1 py-2 text-center num text-xs font-semibold" dir="ltr">
                        {fmtTotal(it.line_total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-slate-800 font-bold">
                    {leading > 0 ? (
                      <td className="px-2 py-2 text-xs text-slate-600" colSpan={leading}>
                        {hasDiscount ? "الإجمالي قبل الخصم" : "الإجمالي"}
                      </td>
                    ) : null}
                    {qtyIdx !== -1 ? (
                      <td className="px-1 py-2 text-center num text-xs whitespace-nowrap" dir="ltr">
                        {Object.entries(qtyByUnit).map(([unit, total]) => (
                          <div key={unit}>{fmtQty(total)} {unit}</div>
                        ))}
                      </td>
                    ) : null}
                    {trailing > 0 ? <td className="px-1 py-2" colSpan={trailing} /> : null}
                    <td className="px-1 py-2 text-center num text-xs" dir="ltr">
                      {fmtTotal(hasDiscount ? inv.items_total : inv.subtotal)}
                    </td>
                  </tr>
                  {hasDiscount ? (
                    <>
                      <tr className="text-slate-600">
                        {cols.length ? (
                          <td className="px-2 py-1.5 text-xs" colSpan={cols.length}>الخصم</td>
                        ) : null}
                        <td className="px-1 py-1.5 text-center num text-xs" dir="ltr">
                          −{fmtTotal(inv.discount)}
                        </td>
                      </tr>
                      <tr className="border-t border-slate-400 font-bold">
                        {cols.length ? (
                          <td className="px-2 py-2 text-xs" colSpan={cols.length}>الإجمالي بعد الخصم</td>
                        ) : null}
                        <td className="px-1 py-2 text-center num text-xs" dir="ltr">
                          {fmtTotal(inv.subtotal)}
                        </td>
                      </tr>
                    </>
                  ) : null}
                </tfoot>
              </table>
            </div>
          </div>
        </div>

        {/* ── Bottom: brand + contact details ───────────────────────── */}
        <div className="relative mt-10 pt-4 border-t-2 border-slate-800" style={{ zIndex: 1 }}>
          <div className="flex items-end justify-between gap-6">
            <div className="text-right">
              <div className="text-xl font-black text-brand leading-none">SEZER</div>
              <div className="text-xs text-slate-500 mt-0.5">لتجارة الأقمشة</div>
            </div>
            <div className="text-left text-xs text-slate-600">
              <div>مصطفى غنام <span className="num inline-block" dir="ltr">0967518466</span></div>
              <div className="text-[11px] text-slate-400 mt-0.5">جميع المبالغ بالدولار الأمريكي</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
