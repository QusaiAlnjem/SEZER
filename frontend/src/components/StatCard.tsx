import type { LucideIcon } from "lucide-react";

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "slate",
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: LucideIcon;
  tone?: "slate" | "green" | "red" | "amber" | "brand";
}) {
  const toneMap: Record<string, string> = {
    slate: "text-slate-800",
    green: "text-emerald-700",
    red: "text-red-700",
    amber: "text-amber-700",
    brand: "text-brand",
  };
  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div className="text-xs text-slate-500">{label}</div>
        {Icon ? <Icon size={16} className="text-slate-400" /> : null}
      </div>
      <div className={`num text-2xl font-extrabold mt-2 ${toneMap[tone]}`}>{value}</div>
      {hint ? <div className="text-xs text-slate-500 mt-1">{hint}</div> : null}
    </div>
  );
}
