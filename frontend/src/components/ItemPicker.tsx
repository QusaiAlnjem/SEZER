"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import type { InventoryItem } from "@/types";
import { fmtQty } from "@/lib/format";

export function itemLabel(i: InventoryItem): string {
  const bits = [i.quality, i.reference];
  if (i.shade) bits.push(`درجة ${i.shade}`);
  if (i.color) bits.push(i.color);
  if (i.name) bits.push(i.name);
  return bits.filter(Boolean).join(" · ");
}

/** Type-to-search product picker.
 *
 *  A plain <select> stops working once the warehouse holds more than a screenful,
 *  so this filters as you type and only ever renders a short list of matches.
 */
export function ItemPicker({
  items,
  value,
  onChange,
  placeholder = "اكتب للبحث عن صنف...",
}: {
  items: InventoryItem[];
  value: string;
  onChange: (id: string) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef<HTMLDivElement | null>(null);

  const selected = useMemo(() => items.find(i => i.id === value) ?? null, [items, value]);

  const matches = useMemo(() => {
    const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const pool = terms.length
      ? items.filter(i => {
          const hay = [
            i.reference, i.quality, i.color, i.shade, i.name, i.unit,
            i.shade ? `درجة ${i.shade}` : "",
          ].filter(Boolean).join(" ").toLowerCase();
          return terms.every(t => hay.includes(t));
        })
      : items;
    return pool.slice(0, 30);   // never render the whole warehouse
  }, [items, query]);

  // close when clicking elsewhere
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => setActive(0), [query, open]);

  function pick(i: InventoryItem) {
    onChange(i.id);
    setQuery("");
    setOpen(false);
  }

  if (selected && !open) {
    return (
      <div ref={boxRef} className="flex items-center gap-1">
        <button
          type="button"
          className="input !py-1.5 text-right flex-1 truncate hover:bg-slate-50"
          onClick={() => { setOpen(true); setQuery(""); }}
          title={itemLabel(selected)}
        >
          {itemLabel(selected)}
        </button>
        <button
          type="button"
          className="p-1 text-slate-400 hover:text-red-600"
          onClick={() => onChange("")}
          aria-label="إلغاء الاختيار"
        >
          <X size={14} />
        </button>
      </div>
    );
  }

  return (
    <div ref={boxRef} className="relative">
      <Search size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
      <input
        className="input !py-1.5 pr-8"
        placeholder={placeholder}
        value={query}
        autoFocus={open}
        onFocus={() => setOpen(true)}
        onChange={e => { setQuery(e.target.value); setOpen(true); }}
        onKeyDown={e => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive(a => Math.min(a + 1, matches.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActive(a => Math.max(a - 1, 0)); }
          else if (e.key === "Enter" && matches[active]) { e.preventDefault(); pick(matches[active]); }
          else if (e.key === "Escape") setOpen(false);
        }}
      />

      {open ? (
        <div className="absolute z-30 mt-1 w-full max-h-64 overflow-auto scroll-thin rounded-xl border border-slate-200 bg-white shadow-lg">
          {matches.length === 0 ? (
            <div className="px-3 py-2 text-xs text-slate-500">لا توجد نتائج</div>
          ) : (
            matches.map((i, idx) => (
              <button
                key={i.id}
                type="button"
                className={`w-full text-right px-3 py-2 text-xs border-b border-slate-50 last:border-0 ${
                  idx === active ? "bg-brand/10" : "hover:bg-slate-50"
                }`}
                onMouseEnter={() => setActive(idx)}
                onClick={() => pick(i)}
              >
                <div className="font-semibold text-slate-800 truncate">{itemLabel(i)}</div>
                <div className="text-slate-500">
                  المتوفر: <span className="num">{fmtQty(i.qty_on_hand)} {i.unit}</span>
                </div>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
