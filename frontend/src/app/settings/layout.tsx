"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { ConsoleShell, ConsoleTopBar } from "@/components/console/ConsoleShell";
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

  const currentTab = SETTINGS_TABS.find((tab) => tab.href === pathname);

  return (
    <ConsoleShell>
      <ConsoleTopBar title={currentTab?.label ?? "Reglas de pago"} caption="Reglas de pago" />
      <main className="w-full max-w-5xl flex-1 px-4 py-6 md:px-8">{children}</main>
    </ConsoleShell>
  );
}
