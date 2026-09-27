"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { DashboardData, ProductSales } from "@/types";
import { fmtTotal, fmtQty, fmtDate } from "@/lib/format";
import { StatCard } from "@/components/StatCard";
import { ProfitChart } from "@/components/ProfitChart";
import {
  ArrowDown, ArrowUp, Users, Boxes, Wallet, AlertTriangle,
  ChevronRight, ChevronLeft, TrendingUp, TrendingDown, RotateCcw, UserPlus,
} from "lucide-react";

/** Range presets, capped at one year. */
const RANGES = [
  { days: 7, label: "٧ أيام" },
  { days: 30, label: "٣٠ يومًا" },
  { days: 90, label: "٣ أشهر" },
  { days: 180, label: "٦ أشهر" },
  { days: 365, label: "سنة" },
];

function isoShift(iso: string, deltaDays: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + deltaDays);
  return d.toISOString().slice(0, 10);
}

function todayIso(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [days, setDays] = useState(30);
  const [end, setEnd] = useState<string>(todayIso());
  const [gran, setGran] = useState<"auto" | "day" | "month">("auto");

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const p = new URLSearchParams({ days: String(days), end, granularity: gran });
      setData(await api.get<DashboardData>(`/api/dashboard?${p}`));
    } catch (e: any) { setErr(e.message); } finally { setLoading(false); }
  }, [days, end, gran]);

  useEffect(() => { load(); }, [load]);

  if (err) return <div className="card text-red-700">{err}</div>;
  if (!data) return <div className="card">جارٍ التحميل...</div>;

  const t = data.totals;
  const today = data.today;
  const atToday = end === todayIso();
  const profitUp = Number(t.net_margin_usd) >= 0;

  return (
    <div className="space-y-4 md:space-y-6">
      <header className="flex items-end justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-800">لوحة التحكم</h1>
        </div>
      </header>

      {/* Today ribbon */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3">
        <StatCard label="إيرادات اليوم" value={fmtTotal(today.inflow_usd)} icon={ArrowDown} tone="green" />
        <StatCard label="مصروفات اليوم" value={fmtTotal(today.outflow_usd)} icon={ArrowUp} tone="red" />
        <StatCard label="صافي اليوم" value={fmtTotal(today.net_usd)} icon={Wallet} tone={Number(today.net_usd) >= 0 ? "green" : "red"} />
        <StatCard label="مستحقات على الزبائن" value={fmtTotal(t.outstanding_ar_usd)} icon={AlertTriangle} tone={Number(t.outstanding_ar_usd) > 0 ? "amber" : "slate"} />
      </div>

      {/* Profit chart + filters */}
      <div className="card">
        <div className="flex items-start justify-between gap-2 flex-wrap mb-3">
          <div>
            <div className="font-bold">الإيرادات والمصروفات والربح</div>
            <div className="text-xs text-slate-500">
              <span className="num">{data.range_from}</span> — <span className="num">{data.range_to}</span>
              {" · "}
              {data.granularity === "day" ? "عرض يومي" : "عرض شهري"}
              {loading ? " · جارٍ التحديث..." : ""}
            </div>
          </div>
          <div className={`text-left ${profitUp ? "text-emerald-700" : "text-red-700"}`}>
            <div className="text-xs text-slate-500">الربح في الفترة</div>
            <div className="num text-xl font-extrabold flex items-center gap-1">
              {profitUp ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
              {fmtTotal(t.net_margin_usd)}
            </div>
          </div>
        </div>

        {/* range presets */}
        <div className="flex gap-1 flex-wrap mb-2">
          {RANGES.map(r => (
            <button
              key={r.days}
              onClick={() => setDays(r.days)}
              className={`px-3 py-2 rounded-lg text-xs ${
                days === r.days ? "bg-brand text-white" : "bg-slate-100 text-slate-700"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>

        {/* granularity + paging through history */}
        <div className="flex items-center gap-1 flex-wrap mb-3">
          {(["auto", "day", "month"] as const).map(g => (
            <button
              key={g}
              onClick={() => setGran(g)}
              className={`px-3 py-2 rounded-lg text-xs ${
                gran === g ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-600"
              }`}
            >
              {g === "auto" ? "تلقائي" : g === "day" ? "أيام" : "أشهر"}
            </button>
          ))}
          <div className="flex-1" />
          <button
            className="btn-ghost !py-2 !px-3 text-xs"
            onClick={() => setEnd(e => isoShift(e, -days))}
            disabled={!data.has_earlier}
            title="فترة سابقة"
          >
            <ChevronRight size={14} /> السابق
          </button>
          <button
            className="btn-ghost !py-2 !px-3 text-xs"
            onClick={() => setEnd(e => {
              const next = isoShift(e, days);
              return next > todayIso() ? todayIso() : next;
            })}
            disabled={atToday}
            title="فترة تالية"
          >
            التالي <ChevronLeft size={14} />
          </button>
          {!atToday ? (
            <button className="btn-ghost !py-2 !px-3 text-xs" onClick={() => setEnd(todayIso())}>
              <RotateCcw size={13} /> اليوم
            </button>
          ) : null}
        </div>

        <ProfitChart data={data.series} height={230} />

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3 pt-3 border-t border-slate-100 text-center">
          <div>
            <div className="text-[11px] text-slate-500">الإيرادات</div>
            <div className="num font-bold text-emerald-700">{fmtTotal(t.revenue_usd)}</div>
          </div>
          <div>
            <div className="text-[11px] text-slate-500">المصروفات</div>
            <div className="num font-bold text-red-700">
              {fmtTotal(Number(t.cogs_usd) + Number(t.opex_usd) + Number(t.purchases_usd))}
            </div>
          </div>
          <div>
            <div className="text-[11px] text-slate-500">منها أوامر الشراء</div>
            <div className="num font-bold text-slate-600">{fmtTotal(t.purchases_usd)}</div>
          </div>
          <div>
            <div className="text-[11px] text-slate-500">
              الربح {t.net_margin_pct !== null ? `(${t.net_margin_pct.toFixed(0)}%)` : ""}
            </div>
            <div className={`num font-bold ${profitUp ? "text-emerald-700" : "text-red-700"}`}>
              {fmtTotal(t.net_margin_usd)}
            </div>
          </div>
        </div>
      </div>

      {/* Movers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 md:gap-4">
        <ProductList
          title="الأكثر مبيعًا"
          hint="ضمن الفترة المحددة"
          icon={TrendingUp}
          tone="emerald"
          rows={data.top_products}
        />
        <ProductList
          title="الأقل مبيعًا"
          hint="من الأصناف التي تحرّكت في الفترة"
          icon={TrendingDown}
          tone="amber"
          rows={data.slow_products}
        />
      </div>

      {/* Customers */}
      <div className="card">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="font-bold">الزبائن</div>
          <Link href="/creditors" className="text-xs text-brand font-semibold py-2 px-1 -my-1">عرض الكل</Link>
        </div>
        <div className="flex items-center gap-3 mb-3 rounded-xl bg-brand/5 p-3">
          <div className="w-11 h-11 rounded-xl bg-brand/15 text-brand grid place-items-center shrink-0">
            <UserPlus size={20} />
          </div>
          <div>
            <div className="num text-2xl font-extrabold text-slate-800 leading-none">
              {data.customers_this_month}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">زبون اشترى هذا الشهر</div>
          </div>
        </div>
        {data.sample_customers.length ? (
          <div className="space-y-1.5">
            {data.sample_customers.map(c => (
              <div key={c.id} className="flex items-center gap-3 rounded-lg border border-slate-100 px-3 py-2">
                <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-500 grid place-items-center text-xs font-bold shrink-0">
                  {c.name.trim().charAt(0)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-sm truncate">{c.name}</div>
                  {c.city ? <div className="text-[11px] text-slate-500">{c.city}</div> : null}
                </div>
                {c.phone ? <div className="num text-xs text-slate-500" dir="ltr">{c.phone}</div> : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">لا يوجد زبائن بعد.</p>
        )}
      </div>

      {/* Quick nav */}
      <div className="grid grid-cols-2 gap-2 sm:gap-3">
        <Quick href="/creditors" label="أمر بيع جديد" hint={`${t.open_so_count} فاتورة مفتوحة`} icon={Users} />
        <Quick href="/storage" label="استلام بضاعة" hint={`${t.low_stock_count} صنف تحت الحد`} icon={Boxes} />
      </div>
    </div>
  );
}

function ProductList({
  title, hint, icon: Icon, tone, rows,
}: {
  title: string; hint: string; icon: any;
  tone: "emerald" | "amber"; rows: ProductSales[];
}) {
  const toneCls = tone === "emerald"
    ? "bg-emerald-50 text-emerald-700"
    : "bg-amber-50 text-amber-700";
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-8 h-8 rounded-lg grid place-items-center shrink-0 ${toneCls}`}>
          <Icon size={16} />
        </div>
        <div className="min-w-0">
          <div className="font-bold leading-tight">{title}</div>
          <div className="text-[11px] text-slate-500">{hint}</div>
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-slate-500">لا توجد مبيعات في هذه الفترة.</p>
      ) : (
        <div className="space-y-1.5">
          {rows.map((p, i) => (
            <div key={p.inventory_item_id} className="flex items-center gap-2 rounded-lg border border-slate-100 px-2.5 py-2">
              <span className={`w-6 h-6 rounded-md grid place-items-center text-xs font-bold shrink-0 ${toneCls}`}>
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-xs font-semibold text-slate-800 truncate" title={p.label}>{p.label}</div>
                <div className="text-[11px] text-slate-500 num">
                  {fmtQty(p.qty_sold)} {p.unit}
                </div>
              </div>
              <div className="num text-sm font-bold text-slate-800 shrink-0">{fmtTotal(p.revenue_usd)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Quick({ href, label, hint, icon: Icon }: { href: string; label: string; hint: string; icon: any }) {
  return (
    <Link href={href} className="card hover:bg-slate-50 transition flex items-center gap-3">
      <div className="w-10 h-10 rounded-xl bg-brand/10 text-brand grid place-items-center shrink-0">
        <Icon size={20} />
      </div>
      <div className="min-w-0">
        <div className="font-semibold text-slate-800 text-sm sm:text-base truncate">{label}</div>
        <div className="text-xs text-slate-500 truncate">{hint}</div>
      </div>
    </Link>
  );
}
