"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { fmtDate, fmtQty, fmtTotal } from "@/lib/format";
import { Printer, CheckCircle2 } from "lucide-react";

type StatementOrder = {
  order_number: string;
  order_date: string;
  subtotal: string;
  paid_amount: string;
  outstanding: string;
  fully_paid: boolean;
};

type StatementPayment = {
  paid_at: string;
  amount: string;
  method: "cash" | "bank" | "remittance" | "other";
  order_number?: string | null;
};

type StatementProduct = {
  label: string;
  unit?: string | null;
  qty: string;
  spent: string;
};

type Statement = {
  statement_number: string;
  issued_at: string;
  period_from: string;
  period_to: string;
  customer_name: string;
  customer_phone?: string | null;
  customer_city?: string | null;
  orders: StatementOrder[];
  period_invoiced: string;
  period_paid: string;
  period_outstanding: string;
  payments: StatementPayment[];
  top_products: StatementProduct[];
  total_outstanding: string;
  older_outstanding: string;
};

const METHODS: Record<StatementPayment["method"], string> = {
  cash: "نقدًا",
  bank: "حوالة بنكية",
  remittance: "حوالة",
  other: "أخرى",
};

export default function StatementPage() {
  const params = useParams<{ id: string }>();
  const [st, setSt] = useState<Statement | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.get<Statement>(`/api/creditors/statements/${params.id}`)
      .then(setSt)
      .catch(e => setErr(e.message));
  }, [params.id]);

  useEffect(() => {
    if (!st) return;
    const t = setTimeout(() => window.print(), 400);
    return () => clearTimeout(t);
  }, [st]);

  if (err) return <div className="p-8 text-red-700">{err}</div>;
  if (!st) return <div className="p-8 text-slate-500">جارٍ التحميل...</div>;

  return (
    <div className="invoice-root bg-white text-slate-900 min-h-screen">
      <style jsx global>{`
        @page { size: A4; margin: 14mm; }
        @media print {
          .no-print { display: none !important; }
          .invoice-root { padding: 0 !important; }
          /* keep the watermark when printing — browsers drop backgrounds by default */
          * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
          .avoid-break { break-inside: avoid; }
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

      <div className="no-print sticky top-0 z-20 bg-slate-100 border-b border-slate-200 px-4 py-2 flex justify-between items-center gap-2 flex-wrap">
        <span className="text-sm text-slate-600">استخدم «حفظ كـ PDF» في نافذة الطباعة</span>
        <button className="btn-primary !py-1.5" onClick={() => window.print()}>
          <Printer size={14} /> طباعة
        </button>
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
          {/* ── Top: brand + who this statement is for ─────────────── */}
          <div className="text-right border-b-2 border-slate-800 pb-4">
            <div className="text-2xl font-black text-brand leading-none">SEZER</div>
            <div className="text-sm font-bold text-slate-800 mt-1">كشف حساب</div>

            <div className="mt-3 text-xs text-slate-600">
              <div className="text-[11px] text-slate-400">الزبون</div>
              <div className="text-base font-bold text-slate-900">{st.customer_name}</div>
              {st.customer_phone ? (
                <div className="num inline-block" dir="ltr">{st.customer_phone}</div>
              ) : null}
              {st.customer_city ? <div>{st.customer_city}</div> : null}
              <div className="mt-1.5">
                رقم الكشف:{" "}
                <span className="num font-semibold inline-block whitespace-nowrap" dir="ltr">
                  {st.statement_number}
                </span>
              </div>
              <div>
                الفترة: <span className="num">{fmtDate(st.period_from)}</span>
                {" — "}
                <span className="num">{fmtDate(st.period_to)}</span>
              </div>
            </div>
          </div>

          {/* ── Headline balance ───────────────────────────────────── */}
          <div className="mt-6 flex flex-col sm:flex-row items-stretch gap-4 avoid-break print:flex-row">
            <div className="w-full sm:w-40 shrink-0 print:w-40">
              <div className="bg-slate-100/90 text-[11px] font-medium px-2 py-2 text-center">
                الرصيد المتبقي
              </div>
              <div className="border-b border-slate-100 px-2 py-3 text-center">
                <span className="num text-lg font-black" dir="ltr">
                  {fmtTotal(st.total_outstanding)}
                </span>
              </div>
            </div>

            <div className="flex-1 grid grid-cols-1 sm:grid-cols-3 print:grid-cols-3 gap-2 text-center self-start">
              <Box label="مفوتر خلال الفترة" value={fmtTotal(st.period_invoiced)} />
              <Box label="مدفوع خلال الفترة" value={fmtTotal(st.period_paid)} />
              <Box label="متبقٍ من فواتير الفترة" value={fmtTotal(st.period_outstanding)} />
            </div>
          </div>

          {Number(st.older_outstanding) > 0 ? (
            <p className="mt-2 text-[11px] text-slate-500">
              يشمل الرصيد المتبقي مبلغ{" "}
              <span className="num font-semibold">{fmtTotal(st.older_outstanding)}</span>{" "}
              من فواتير أقدم من هذه الفترة.
            </p>
          ) : null}

          {/* ── Invoices in the period ─────────────────────────────── */}
          <Section title={`الفواتير خلال الفترة (${st.orders.length})`}>
            {st.orders.length === 0 ? (
              <Empty>لا توجد فواتير في هذه الفترة.</Empty>
            ) : (
              <table className="w-full min-w-[520px] text-sm table-fixed print:min-w-0">
                <thead>
                  <tr className="bg-slate-100/90 text-[11px]">
                    <th className="px-2 py-2 text-right">رقم الفاتورة</th>
                    <th className="px-1 py-2 text-center w-24">التاريخ</th>
                    <th className="px-1 py-2 text-center w-24">الإجمالي</th>
                    <th className="px-1 py-2 text-center w-24">المدفوع</th>
                    <th className="px-1 py-2 text-center w-24">المتبقي</th>
                    <th className="px-1 py-2 text-center w-20">الحالة</th>
                  </tr>
                </thead>
                <tbody>
                  {st.orders.map(o => (
                    <tr key={o.order_number} className="border-b border-slate-100">
                      <td className="px-2 py-2 num text-xs" dir="ltr">{o.order_number}</td>
                      <td className="px-1 py-2 text-center num text-xs">{fmtDate(o.order_date)}</td>
                      <td className="px-1 py-2 text-center num text-xs" dir="ltr">{fmtTotal(o.subtotal)}</td>
                      <td className="px-1 py-2 text-center num text-xs" dir="ltr">{fmtTotal(o.paid_amount)}</td>
                      <td className="px-1 py-2 text-center num text-xs font-semibold" dir="ltr">
                        {fmtTotal(o.outstanding)}
                      </td>
                      <td className="px-1 py-2 text-center text-[11px]">
                        {o.fully_paid ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700">
                            <CheckCircle2 size={11} /> مسدّدة
                          </span>
                        ) : (
                          <span className="text-amber-800">متبقٍ رصيد</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-slate-800 font-bold">
                    <td className="px-2 py-2 text-xs text-slate-600" colSpan={2}>الإجمالي</td>
                    <td className="px-1 py-2 text-center num text-xs" dir="ltr">{fmtTotal(st.period_invoiced)}</td>
                    <td className="px-1 py-2" />
                    <td className="px-1 py-2 text-center num text-xs" dir="ltr">{fmtTotal(st.period_outstanding)}</td>
                    <td className="px-1 py-2" />
                  </tr>
                </tfoot>
              </table>
            )}
          </Section>

          {/* ── Payments received ──────────────────────────────────── */}
          <Section title={`سجل الدفعات (${st.payments.length})`}>
            {st.payments.length === 0 ? (
              <Empty>لا توجد دفعات في هذه الفترة.</Empty>
            ) : (
              <table className="w-full min-w-[520px] text-sm table-fixed print:min-w-0">
                <thead>
                  <tr className="bg-slate-100/90 text-[11px]">
                    <th className="px-2 py-2 text-right w-28">التاريخ</th>
                    <th className="px-1 py-2 text-right">على الفاتورة</th>
                    <th className="px-1 py-2 text-center w-28">الطريقة</th>
                    <th className="px-1 py-2 text-center w-28">المبلغ</th>
                  </tr>
                </thead>
                <tbody>
                  {st.payments.map((p, idx) => (
                    <tr key={idx} className="border-b border-slate-100">
                      <td className="px-2 py-2 num text-xs">{fmtDate(p.paid_at)}</td>
                      <td className="px-1 py-2 num text-xs" dir="ltr">{p.order_number || "—"}</td>
                      <td className="px-1 py-2 text-center text-xs">{METHODS[p.method]}</td>
                      <td className="px-1 py-2 text-center num text-xs font-semibold" dir="ltr">
                        {fmtTotal(p.amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-slate-800 font-bold">
                    <td className="px-2 py-2 text-xs text-slate-600" colSpan={3}>إجمالي المدفوع</td>
                    <td className="px-1 py-2 text-center num text-xs" dir="ltr">{fmtTotal(st.period_paid)}</td>
                  </tr>
                </tfoot>
              </table>
            )}
          </Section>

          {/* ── Most-bought products ───────────────────────────────── */}
          <Section title="الأصناف الأكثر شراءً">
            {st.top_products.length === 0 ? (
              <Empty>لا توجد مشتريات في هذه الفترة.</Empty>
            ) : (
              <table className="w-full min-w-[520px] text-sm table-fixed print:min-w-0">
                <thead>
                  <tr className="bg-slate-100/90 text-[11px]">
                    <th className="px-2 py-2 text-center w-10">#</th>
                    <th className="px-1 py-2 text-right">الصنف</th>
                    <th className="px-1 py-2 text-center w-32">الكمية</th>
                    <th className="px-1 py-2 text-center w-28">القيمة</th>
                  </tr>
                </thead>
                <tbody>
                  {st.top_products.map((p, idx) => (
                    <tr key={p.label} className="border-b border-slate-100">
                      <td className="px-2 py-2 text-center num text-xs">{idx + 1}</td>
                      <td className="px-1 py-2 text-xs">{p.label}</td>
                      <td className="px-1 py-2 text-center num text-xs whitespace-nowrap" dir="ltr">
                        {fmtQty(p.qty)} {p.unit ?? ""}
                      </td>
                      <td className="px-1 py-2 text-center num text-xs" dir="ltr">{fmtTotal(p.spent)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>
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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6 avoid-break">
      <div className="text-sm font-bold text-slate-800 mb-2">{title}</div>
      {/* tables stay legible on a phone by scrolling, never by shrinking */}
      <div className="overflow-x-auto scroll-thin print:overflow-visible">{children}</div>
    </div>
  );
}

function Box({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-slate-200 px-2 py-2">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="num font-bold text-slate-900" dir="ltr">{value}</div>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-slate-500 py-2">{children}</p>;
}
