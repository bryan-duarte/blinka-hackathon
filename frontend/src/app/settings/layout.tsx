"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { tokenStore } from "@/lib/api";

const SETTINGS_TABS = [
  { href: "/settings/policy", label: "Política" },
  { href: "/settings/payees", label: "Beneficiarios" },
  { href: "/settings/blacklist", label: "Lista negra" },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!tokenStore.get()) router.replace("/login");
  }, [router]);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 pt-3 md:px-6">
          <div className="flex items-center justify-between gap-3">
            <h1 className="text-base font-[450] tracking-[-0.02em] text-ink">Reglas de pago</h1>
            <Link
              href="/inbox"
              className="rounded px-1 text-sm text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
            >
              ← Volver a la bandeja
            </Link>
          </div>
          <nav aria-label="Configuración" className="-mb-px flex gap-1 overflow-x-auto">
            {SETTINGS_TABS.map((tab) => {
              const isCurrent = pathname === tab.href;
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  aria-current={isCurrent ? "page" : undefined}
                  className={`shrink-0 border-b-2 px-3 py-2.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-accent ${isCurrent ? "border-accent font-medium text-ink" : "border-transparent text-muted hover:text-ink"}`}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 md:px-6">{children}</main>
    </div>
  );
}
