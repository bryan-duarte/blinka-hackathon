"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { ConsoleShell, ConsoleTopBar } from "@/components/console/ConsoleShell";
import { tokenStore } from "@/lib/api";

const SETTINGS_TABS = [
  { href: "/settings/policy", label: "Policy" },
  { href: "/settings/payees", label: "Payees" },
  { href: "/settings/blacklist", label: "Blacklist" },
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
      <ConsoleTopBar title={currentTab?.label ?? "Payment rules"} caption="Payment rules" />
      <main className="w-full max-w-5xl flex-1 px-4 py-6 md:px-8">{children}</main>
    </ConsoleShell>
  );
}
