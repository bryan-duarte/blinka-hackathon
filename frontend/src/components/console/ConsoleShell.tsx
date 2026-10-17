"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Wordmark } from "@/components/brand/Wordmark";
import { PAGE_HEADING_CLASS } from "@/components/settings/styles";
import { tokenStore } from "@/lib/api";

type NavItem = { href: string; label: string };

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Pagos",
    items: [
      { href: "/inbox", label: "Bandeja" },
      { href: "/bills", label: "Cola de revisión" },
    ],
  },
  {
    label: "Reglas de pago",
    items: [
      { href: "/settings/policy", label: "Política" },
      { href: "/settings/payees", label: "Beneficiarios" },
      { href: "/settings/blacklist", label: "Lista negra" },
    ],
  },
];

const NAV_ITEMS = NAV_GROUPS.flatMap((group) => group.items);

const NAV_LINK_CLASS =
  "flex min-h-10 shrink-0 items-center rounded px-3 text-sm font-normal transition-colors focus-visible:outline-2 focus-visible:outline-accent";

function navLinkClass(isCurrent: boolean): string {
  return `${NAV_LINK_CLASS} ${isCurrent ? "bg-accent-wash text-accent" : "text-ink hover:bg-sunken"}`;
}

export function ConsoleShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  function logout() {
    tokenStore.clear();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen md:flex">
      <aside className="hidden w-62 shrink-0 flex-col gap-8 border-r border-line bg-panel px-4 py-6 md:sticky md:top-0 md:flex md:h-screen">
        <Link href="/" className="self-start rounded px-3 focus-visible:outline-2 focus-visible:outline-accent">
          <Wordmark />
        </Link>
        {NAV_GROUPS.map((group) => (
          <nav key={group.label} aria-label={group.label} className="flex flex-col gap-1">
            <p className="px-3 pb-2 text-xs tracking-[0.5px] text-muted uppercase">{group.label}</p>
            {group.items.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={pathname === item.href ? "page" : undefined}
                className={navLinkClass(pathname === item.href)}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        ))}
        <div className="mt-auto border-t border-line pt-4">
          <button type="button" onClick={logout} className={`${navLinkClass(false)} w-full text-muted`}>
            Salir
          </button>
        </div>
      </aside>

      <header className="border-b border-line bg-panel md:hidden">
        <div className="flex items-center justify-between px-4 pt-3">
          <Link href="/" className="rounded focus-visible:outline-2 focus-visible:outline-accent">
            <Wordmark />
          </Link>
          <button type="button" onClick={logout} className={`${navLinkClass(false)} text-muted`}>
            Salir
          </button>
        </div>
        <nav aria-label="Consola" className="flex gap-1 overflow-x-auto px-4 py-2">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={pathname === item.href ? "page" : undefined}
              className={navLinkClass(pathname === item.href)}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </header>

      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}

type ConsoleTopBarProps = {
  title: string;
  caption?: string;
  actions?: React.ReactNode;
};

export function ConsoleTopBar({ title, caption, actions }: ConsoleTopBarProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line bg-panel px-4 py-4 md:px-8">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className={PAGE_HEADING_CLASS}>{title}</h1>
        {caption && <p className="text-xs text-muted">{caption}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
