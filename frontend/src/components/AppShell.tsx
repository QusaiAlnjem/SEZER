"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LayoutDashboard, Users, Boxes, Truck, LogOut, Menu, X } from "lucide-react";
import { getToken, logout } from "@/lib/api";

const NAV = [
  { href: "/",           label: "الرئيسية",  icon: LayoutDashboard },
  { href: "/suppliers",  label: "الموردون",   icon: Truck },
  { href: "/creditors",  label: "الزبائن",     icon: Users },
  { href: "/storage",    label: "المستودع",     icon: Boxes },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  // print surfaces get no sidebar and no chrome
  const bare =
    pathname === "/login" ||
    pathname.startsWith("/invoice/") ||
    pathname.startsWith("/statement/");

  // null while the saved sign-in is still being read
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    if (bare) return;
    const ok = !!getToken();
    setAuthed(ok);
    if (!ok) router.replace("/login");
  }, [bare, pathname, router]);

  if (bare) return <>{children}</>;

  // Hold the page back until we know. Rendering children first would mount
  // the dashboard, fire its requests without a token, and flash both the app
  // and a 401 error before the redirect landed.
  if (authed !== true) return <div className="min-h-screen bg-slate-50" />;

  return (
    <div className="min-h-screen flex flex-col md:flex-row" dir="rtl">
      {/* Top bar (mobile) */}
      <header className="md:hidden sticky top-0 z-30 flex items-center justify-between bg-white border-b border-slate-200 px-4 py-3">
        <button
          className="p-2 rounded-lg hover:bg-slate-100"
          onClick={() => setOpen((v) => !v)}
          aria-label="القائمة"
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
        <div className="flex items-center gap-2">
          <span className="text-brand font-extrabold text-lg">SEZER</span>
          <span className="text-xs text-slate-500">إدارة أقمشة</span>
        </div>
        <button className="p-2 rounded-lg hover:bg-slate-100" onClick={logout} aria-label="خروج">
          <LogOut size={18} />
        </button>
      </header>

      {/* Sidebar */}
      <aside
        className={`${open ? "block" : "hidden"} md:block bg-white border-l border-slate-200 md:w-64 md:min-h-screen md:sticky md:top-0`}
      >
        <div className="hidden md:flex items-center gap-2 px-5 py-5 border-b border-slate-100">
          <div className="w-9 h-9 rounded-xl bg-brand text-white grid place-items-center font-black">S</div>
          <div>
            <div className="text-brand font-extrabold text-lg leading-none">SEZER</div>
            <div className="text-xs text-slate-500">إدارة أقمشة</div>
          </div>
        </div>
        <nav className="p-3 space-y-1">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm ${
                  active ? "bg-brand/10 text-brand font-semibold" : "hover:bg-slate-50 text-slate-700"
                }`}
              >
                <Icon size={18} />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="hidden md:block p-3 border-t border-slate-100 mt-auto">
          <button className="btn-ghost w-full justify-start" onClick={logout}>
            <LogOut size={16} /> خروج
          </button>
        </div>
      </aside>

      <main className="flex-1 p-4 md:p-6 max-w-full">{children}</main>
    </div>
  );
}
