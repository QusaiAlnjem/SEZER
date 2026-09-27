/** Money with cents — for unit prices, where 4.5 must not become 5. */
export function fmtMoney(n: number | string): string {
  const val = Number(n ?? 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", maximumFractionDigits: 2,
  }).format(val);
}

/** Whole-dollar totals: thousands separators, no trailing ".00". */
export function fmtTotal(n: number | string): string {
  const val = Number(n ?? 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", maximumFractionDigits: 0,
  }).format(val);
}

export function fmtQty(n: number | string): string {
  const val = Number(n ?? 0);
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 }).format(val);
}

export function fmtDate(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return d.toLocaleDateString("ar-EG", { year: "numeric", month: "short", day: "2-digit" });
}

export function fmtDateTime(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return d.toLocaleString("ar-EG", { dateStyle: "short", timeStyle: "short" });
}

export function today(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
