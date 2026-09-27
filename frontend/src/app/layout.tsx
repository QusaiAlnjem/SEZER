import type { Metadata, Viewport } from "next";
import "@/styles/globals.css";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "SEZER — إدارة الأقمشة",
  description: "لوحة تحكم أعمال SEZER للأقمشة: التدفق النقدي، المستوردون، الزبائن، الشحن والجمارك، والمستودع.",
  manifest: "/manifest.json",
  applicationName: "SEZER",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "SEZER" },
  icons: { icon: "/icons/icon-192.png", apple: "/icons/icon-192.png" },
};

export const viewport: Viewport = {
  themeColor: "#0f766e",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
