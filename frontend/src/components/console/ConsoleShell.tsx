"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Wordmark } from "@/components/brand/Wordmark";
import { PAGE_HEADING_CLASS } from "@/components/settings/styles";
import { api, tokenStore } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { MailProvider } from "@/lib/types";

type NavIcon = "approvals" | "inbox" | "decisions" | "runs" | "policy" | "payees" | "blocked";

type NavItem = { href: string; label: string; icon: NavIcon; countsApprovals?: boolean };

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Work",
    items: [
      { href: "/bills", label: "Approvals", icon: "approvals", countsApprovals: true },
      { href: "/inbox", label: "Inbox", icon: "inbox" },
      { href: "/ledger", label: "Decisions", icon: "decisions" },
      { href: "/runs", label: "Agent runs", icon: "runs" },
    ],
  },
  {
    label: "Rules",
    items: [
      { href: "/settings/policy", label: "Payment policy", icon: "policy" },
      { href: "/settings/payees", label: "Payees", icon: "payees" },
      { href: "/settings/blacklist", label: "Blocked list", icon: "blocked" },
    ],
  },
];

const NAV_ITEMS = NAV_GROUPS.flatMap((group) => group.items);

const NAV_ICON_PATHS: Record<NavIcon, React.ReactNode> = {
  approvals: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v5M12 16h.01" />
    </>
  ),
  inbox: (
    <>
      <path d="M4 13l2.5-7h11L20 13v6H4z" />
      <path d="M4 13h5l1 2h4l1-2h5" />
    </>
  ),
  decisions: (
    <>
      <path d="M6 4h12v16H6z" />
      <path d="M9 8h6M9 12h6M9 16h4" />
    </>
  ),
  runs: <path d="M3 12h4l2-5 4 10 2-5h6" />,
  policy: (
    <>
      <path d="M4 6h3M11 6h9M4 12h9M17 12h3M4 18h1M9 18h11" />
      <circle cx="9" cy="6" r="2" />
      <circle cx="15" cy="12" r="2" />
      <circle cx="7" cy="18" r="2" />
    </>
  ),
  payees: (
    <>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6M16 5a3 3 0 010 6M18 14c2 .8 3 2.8 3 6" />
    </>
  ),
  blocked: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M6.5 6.5l11 11" />
    </>
  ),
};

const CHANNEL_LABELS: Record<MailProvider, string> = {
  gmail: "Gmail",
  outlook: "Outlook",
  simulated: "the demo inbox",
  whatsapp: "WhatsApp",
};

const channelListFormatter = new Intl.ListFormat("en-US", { style: "long", type: "conjunction" });

const NAV_LINK_CLASS =
  "flex min-h-9 shrink-0 items-center gap-2.5 rounded px-2.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";

const GROUP_LABEL_CLASS = "mx-2.5 mt-4 mb-1.5 text-sm font-bold text-muted [font-variant-caps:all-small-caps]";

type AgentStatus = {
  channels: string[] | null;
  lastRunAt: string | null;
  policyVersion: number | null;
  approvalCount: number | null;
};

const UNKNOWN_STATUS: AgentStatus = { channels: null, lastRunAt: null, policyVersion: null, approvalCount: null };

function isCurrentSection(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function navLinkClass(isCurrent: boolean): string {
  return `${NAV_LINK_CLASS} ${isCurrent ? "bg-ink text-white" : "text-ink hover:bg-sunken"}`;
}

function settledValue<T>(result: PromiseSettledResult<T>): T | null {
  return result.status === "fulfilled" ? result.value : null;
}

function useAgentStatus(): AgentStatus {
  const [status, setStatus] = useState<AgentStatus>(UNKNOWN_STATUS);
  useEffect(() => {
    if (!tokenStore.get()) return;
    let isCancelled = false;
    Promise.allSettled([api.connections(), api.runs(), api.policy(), api.bills("review")]).then(
      ([connections, runs, policy, approvals]) => {
        if (isCancelled) return;
        const activeProviders = settledValue(connections)
          ?.filter((connection) => connection.status === "active")
          .map((connection) => CHANNEL_LABELS[connection.provider]);
        setStatus({
          channels: activeProviders ? [...new Set(activeProviders)] : null,
          lastRunAt: settledValue(runs)?.[0]?.created_at ?? null,
          policyVersion: settledValue(policy)?.version ?? null,
          approvalCount: settledValue(approvals)?.length ?? null,
        });
      },
    );
    return () => {
      isCancelled = true;
    };
  }, []);
  return status;
}

function NavLink({ item, pathname, approvalCount }: { item: NavItem; pathname: string; approvalCount: number | null }) {
  const isCurrent = isCurrentSection(pathname, item.href);
  return (
    <Link href={item.href} aria-current={isCurrent ? "page" : undefined} className={navLinkClass(isCurrent)}>
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="size-4 flex-none fill-none stroke-current stroke-[1.5]"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {NAV_ICON_PATHS[item.icon]}
      </svg>
      {item.label}
      {item.countsApprovals && approvalCount !== null && approvalCount > 0 && (
        <span className="ml-auto text-xs text-muted tabular-nums">{approvalCount}</span>
      )}
    </Link>
  );
}

function AgentStatusCard({ status }: { status: AgentStatus }) {
  if (status.channels === null) {
    return <div aria-hidden className="mx-1 h-[86px] animate-pulse rounded border border-line bg-sunken" />;
  }
  const isListening = status.channels.length > 0;
  const lastRunParts = [
    status.lastRunAt && `Last run ${formatRelative(status.lastRunAt)}`,
    status.policyVersion !== null && `policy v${status.policyVersion}`,
  ].filter(Boolean);
  return (
    <div className="mx-1 grid gap-1 rounded border border-line p-3.5">
      <span className="flex items-center gap-2 font-medium">
        <span aria-hidden className={`size-2 rounded-full ${isListening ? "bg-ink" : "border border-ink"}`} />
        {isListening ? "Agent is on" : "No channels connected"}
      </span>
      {lastRunParts.length > 0 && <span className="text-xs text-muted">{lastRunParts.join(" · ")}</span>}
      <span className="text-xs text-muted">
        {isListening ? `Listening on ${channelListFormatter.format(status.channels)}` : "Connect one from the inbox"}
      </span>
    </div>
  );
}

export function ConsoleShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const status = useAgentStatus();

  function logout() {
    tokenStore.clear();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen bg-white text-sm md:flex">
      <aside className="hidden w-62 shrink-0 flex-col gap-5 border-r border-line px-3.5 py-5 md:sticky md:top-0 md:flex md:h-screen md:overflow-y-auto">
        <Link
          href="/"
          className="self-start rounded px-2.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          <Wordmark />
        </Link>
        <AgentStatusCard status={status} />
        <nav aria-label="Console" className="flex flex-col gap-0.5">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="flex flex-col gap-0.5">
              <p className={GROUP_LABEL_CLASS}>{group.label}</p>
              {group.items.map((item) => (
                <NavLink key={item.href} item={item} pathname={pathname} approvalCount={status.approvalCount} />
              ))}
            </div>
          ))}
        </nav>
        <div className="mt-auto border-t border-line pt-4">
          <button type="button" onClick={logout} className={`${navLinkClass(false)} w-full text-muted`}>
            Sign out
          </button>
        </div>
      </aside>

      <header className="border-b border-line md:hidden">
        <div className="flex items-center justify-between px-4 pt-3">
          <Link href="/" className="rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
            <Wordmark />
          </Link>
          <button type="button" onClick={logout} className={`${navLinkClass(false)} text-muted`}>
            Sign out
          </button>
        </div>
        <nav aria-label="Console" className="flex gap-1 overflow-x-auto px-4 py-2">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} approvalCount={status.approvalCount} />
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
