"use client";
import { useCallback, useState } from "react";
import { Modal } from "@/components/Modal";
import { AlertTriangle } from "lucide-react";

/** In-app replacement for window.confirm().
 *
 *  The native dialog pulls focus out of the document, and Chrome then refuses
 *  to open the popup for a <select> or an <input type="date"> until the page
 *  is reloaded — so those fields look dead while the rest of the form works.
 *  Keeping the prompt inside the page avoids that entirely, and it can be
 *  written in Arabic and laid out RTL like everything else.
 *
 *  Usage:
 *      const { ask, confirmUi } = useConfirm();
 *      if (!(await ask("حذف هذا؟"))) return;
 *      ...render {confirmUi} once, anywhere in the tree
 */
export function useConfirm() {
  const [pending, setPending] = useState<{
    message: string;
    resolve: (ok: boolean) => void;
  } | null>(null);

  const ask = useCallback(
    (message: string) => new Promise<boolean>(resolve => setPending({ message, resolve })),
    [],
  );

  const settle = (ok: boolean) => {
    pending?.resolve(ok);
    setPending(null);
  };

  const confirmUi = (
    <Modal open={pending !== null} onClose={() => settle(false)} title="تأكيد" size="sm">
      <div className="space-y-4">
        <div className="flex gap-3">
          <AlertTriangle size={20} className="text-amber-500 shrink-0 mt-0.5" />
          <p className="text-sm text-slate-700 whitespace-pre-line leading-relaxed">
            {pending?.message}
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-danger flex-1" onClick={() => settle(true)} autoFocus>
            حذف
          </button>
          <button className="btn-ghost flex-1" onClick={() => settle(false)}>
            إلغاء
          </button>
        </div>
      </div>
    </Modal>
  );

  return { ask, confirmUi };
}
