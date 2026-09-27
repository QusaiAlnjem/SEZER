"use client";
import { useEffect, useState } from "react";
import { Modal } from "@/components/Modal";
import { LogisticsField } from "@/components/LogisticsField";
import { fmtTotal } from "@/lib/format";
import { Truck } from "lucide-react";
import type { SupplierOrder } from "@/types";

export type OrderCosts = {
  shipment_cost: number | null;
  shipping_value: number;
  shipping_is_percent: boolean;
  customs_value: number;
  customs_is_percent: boolean;
};

type Draft = {
  goods: string;
  shipping: string;
  shippingPct: boolean;
  customs: string;
  customsPct: boolean;
};

const blank: Draft = { goods: "", shipping: "", shippingPct: false, customs: "", customsPct: false };

function draftFrom(order?: SupplierOrder | null): Draft {
  if (!order || order.shipment_cost === null || order.shipment_cost === undefined) return { ...blank };
  return {
    goods: String(Number(order.shipment_cost)),
    shipping: Number(order.shipping_value) ? String(Number(order.shipping_value)) : "",
    shippingPct: order.shipping_is_percent,
    customs: Number(order.customs_value) ? String(Number(order.customs_value)) : "",
    customsPct: order.customs_is_percent,
  };
}

/** What a shipment cost: goods, plus shipping and customs as $ or % of goods.
 *
 *  `onSave` gets the three figures; `onSkip` means "carry on without recording
 *  anything" — the caller decides what carrying on does.
 */
export function OrderCostDialog({
  open,
  title,
  order,
  prefill = false,
  saveLabel = "حفظ",
  skipLabel = "تخطٍ",
  busy = false,
  onSave,
  onSkip,
  onDismiss,
}: {
  open: boolean;
  title: string;
  order?: SupplierOrder | null;
  /** Start from the order's stored costs (correcting) rather than empty (first time). */
  prefill?: boolean;
  saveLabel?: string;
  skipLabel?: string;
  busy?: boolean;
  onSave: (costs: OrderCosts) => void;
  onSkip: () => void;
  onDismiss: () => void;
}) {
  const [d, setD] = useState<Draft>(blank);

  // refill whenever a different order opens the dialog
  useEffect(() => {
    if (!open) return;
    setD(prefill ? draftFrom(order) : { ...blank });
  }, [open, prefill, order?.id]);

  const goods = d.goods.trim() === "" ? null : Number(d.goods);
  const goodsInvalid = goods !== null && (!Number.isFinite(goods) || goods < 0);
  // percentages need a base, so they stay inert until the goods total is in
  const noBase = goods === null || goods <= 0;

  const part = (raw: string, isPercent: boolean) => {
    const v = Number(raw || 0);
    if (!Number.isFinite(v) || v <= 0) return 0;
    return isPercent ? ((goods ?? 0) * v) / 100 : v;
  };
  const shippingAmount = part(d.shipping, d.shippingPct);
  const customsAmount = part(d.customs, d.customsPct);
  const total = (goods ?? 0) + shippingAmount + customsAmount;

  const invalid = goodsInvalid || [d.shipping, d.customs].some(
    raw => raw.trim() !== "" && (!Number.isFinite(Number(raw)) || Number(raw) < 0)
  );

  function save() {
    onSave({
      shipment_cost: goods,
      shipping_value: Number(d.shipping || 0),
      shipping_is_percent: d.shippingPct,
      customs_value: Number(d.customs || 0),
      customs_is_percent: d.customsPct,
    });
  }

  return (
    <Modal open={open} onClose={onDismiss} title={title}>
      <div className="space-y-3">
        {order?.order_number ? (
          <div className="text-sm text-slate-600 flex items-center gap-2">
            <Truck size={14} className="text-brand" />
            <span>أمر الشراء</span>
            <span className="num font-bold" dir="ltr">{order.order_number}</span>
          </div>
        ) : null}

        <div>
          <label className="label">تكلفة البضاعة (USD)</label>
          <input
            dir="ltr"
            className="input num"
            inputMode="decimal"
            placeholder="0.00"
            value={d.goods}
            autoFocus
            onChange={e => setD({ ...d, goods: e.target.value })}
            onKeyDown={e => { if (e.key === "Enter" && !invalid && !busy) save(); }}
          />
          {goodsInvalid ? (
            <p className="text-xs text-red-600 mt-1">أدخل مبلغًا صحيحًا (0 أو أكثر).</p>
          ) : null}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <LogisticsField
            label="تكلفة الشحن"
            value={d.shipping}
            isPercent={d.shippingPct}
            amount={shippingAmount}
            disabled={noBase}
            hint={noBase ? "أدخل تكلفة البضاعة أولًا" : undefined}
            onValue={v => setD({ ...d, shipping: v })}
            onMode={p => setD({ ...d, shippingPct: p })}
          />
          <LogisticsField
            label="تكلفة الجمركة"
            value={d.customs}
            isPercent={d.customsPct}
            amount={customsAmount}
            disabled={noBase}
            hint={noBase ? "أدخل تكلفة البضاعة أولًا" : undefined}
            onValue={v => setD({ ...d, customs: v })}
            onMode={p => setD({ ...d, customsPct: p })}
          />
        </div>

        {total > 0 ? (
          <div className="rounded-xl bg-slate-50 px-3 py-2 flex items-center justify-between text-sm">
            <span className="text-slate-600">الإجمالي</span>
            <span className="num font-bold text-slate-800" dir="ltr">{fmtTotal(total)}</span>
          </div>
        ) : null}

        <div className="flex gap-2">
          <button className="btn-primary flex-1" disabled={busy || invalid} onClick={save}>
            {saveLabel}
          </button>
          <button className="btn-ghost" disabled={busy} onClick={onSkip}>
            {skipLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
}
