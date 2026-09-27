"use client";
import { fmtTotal } from "@/lib/format";

/** An amount that is either flat dollars or a percentage of some base. */
export function LogisticsField({
  label, value, isPercent, amount, onValue, onMode, disabled = false, hint,
}: {
  label: string;
  value: string;
  isPercent: boolean;
  amount: number;
  onValue: (v: string) => void;
  onMode: (isPercent: boolean) => void;
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex gap-1">
        <input
          dir="ltr"
          className="input num disabled:bg-slate-50 disabled:text-slate-400"
          inputMode="decimal"
          placeholder="0"
          value={value}
          disabled={disabled}
          onChange={e => onValue(e.target.value)}
        />
        <div className="flex rounded-xl bg-slate-100 p-0.5 shrink-0">
          <button
            type="button"
            className={`px-2.5 py-1 rounded-lg text-xs font-bold ${!isPercent ? "bg-white shadow-sm text-brand" : "text-slate-500"}`}
            onClick={() => onMode(false)}
            disabled={disabled}
          >
            $
          </button>
          <button
            type="button"
            className={`px-2.5 py-1 rounded-lg text-xs font-bold ${isPercent ? "bg-white shadow-sm text-brand" : "text-slate-500"}`}
            onClick={() => onMode(true)}
            disabled={disabled}
          >
            %
          </button>
        </div>
      </div>
      {hint ? (
        <div className="text-[11px] text-slate-400 mt-1">{hint}</div>
      ) : isPercent && amount > 0 ? (
        <div className="text-[11px] text-slate-500 mt-1">
          = <span className="num">{fmtTotal(amount)}</span>
        </div>
      ) : null}
    </div>
  );
}
