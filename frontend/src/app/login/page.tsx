"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { loginWithPin, setToken } from "@/lib/api";
import { Splash } from "@/components/Splash";
import { Lock } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const res = await loginWithPin(pin);
      setToken(res.access_token, res.expires_in);
      router.replace("/");
    } catch (e: any) {
      setErr(e?.message || "خطأ في الدخول");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-gradient-to-br from-brand/10 via-white to-brand/5 p-6" dir="rtl">
      <Splash />
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4">
        <div className="text-center">
          <div className="mx-auto w-12 h-12 rounded-2xl bg-brand text-white grid place-items-center font-black text-xl">S</div>
          <h1 className="mt-3 text-xl font-extrabold text-brand">SEZER</h1>
          <p className="text-xs text-slate-500 mt-1">إدارة أعمال الأقمشة</p>
        </div>

        <div>
          <label className="label"><Lock size={12} className="inline ml-1" /> الرقم السري</label>
          <input
            className="input text-center tracking-widest text-lg"
            type="password"
            inputMode="numeric"
            autoFocus
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            placeholder="****"
          />
        </div>
        {err ? <div className="text-sm text-red-600 text-center">{err}</div> : null}
        <button type="submit" className="btn-primary w-full" disabled={busy || pin.length < 4}>
          {busy ? "جارٍ الدخول..." : "دخول"}
        </button>
      </form>
    </div>
  );
}
