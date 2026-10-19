"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ConsoleShell, ConsoleTopBar } from "@/components/console/ConsoleShell";
import { RunsTable } from "@/components/runs/RunsTable";
import { filterTabClass } from "@/components/settings/styles";
import { UnauthorizedError, api, tokenStore } from "@/lib/api";
import type { RunListItemView, RunStatus } from "@/lib/types";

const ACTIVE_POLL_MS = 5000;
const ACTIVE_STATUSES: ReadonlySet<RunStatus> = new Set(["pending", "running"]);
const STATUS_FILTERS: { status: RunStatus | null; label: string }[] = [
  { status: null, label: "All" },
  { status: "running", label: "Running" },
  { status: "completed", label: "Completed" },
  { status: "failed", label: "Failed" },
];

function isNotABillRun(run: RunListItemView): boolean {
  return run.status === "completed" && run.verdict === null;
}

export default function RunsPage() {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState<RunStatus | null>(null);
  const [runs, setRuns] = useState<RunListItemView[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const hasActiveRuns = (runs ?? []).some((run) => ACTIVE_STATUSES.has(run.status));

  useEffect(() => {
    if (!tokenStore.get()) {
      router.replace("/login");
      return;
    }
    let isCancelled = false;
    const loadRuns = () =>
      api
        .runs(statusFilter ?? undefined)
        .then((loadedRuns) => {
          if (isCancelled) return;
          setRuns(loadedRuns.filter((run) => !isNotABillRun(run)));
          setLoadError(null);
        })
        .catch((error: unknown) => {
          if (isCancelled) return;
          if (error instanceof UnauthorizedError) {
            router.replace("/login");
            return;
          }
          setLoadError("The executions could not be loaded.");
        });
    loadRuns();
    const pollTimer = hasActiveRuns ? setInterval(loadRuns, ACTIVE_POLL_MS) : undefined;
    return () => {
      isCancelled = true;
      clearInterval(pollTimer);
    };
  }, [router, statusFilter, hasActiveRuns]);

  return (
    <ConsoleShell>
      <ConsoleTopBar title="Agent runs" caption="Every run of the payments agent, including failed ones" />
      <main className="flex flex-1 flex-col gap-4 px-4 py-6 md:px-8">
        <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-1">
          {STATUS_FILTERS.map((filter) => {
            const isActive = statusFilter === filter.status;
            return (
              <button
                key={filter.label}
                type="button"
                aria-pressed={isActive}
                onClick={() => {
                  setRuns(null);
                  setStatusFilter(filter.status);
                }}
                className={filterTabClass(isActive)}
              >
                {filter.label}
              </button>
            );
          })}
        </div>
        {loadError && (
          <p role="alert" className="text-sm text-danger">
            <span aria-hidden>✕ </span>
            {loadError}
          </p>
        )}
        <section aria-label="Executions" className="overflow-hidden rounded-lg border border-line bg-panel">
          <RunsTable runs={runs} />
        </section>
      </main>
    </ConsoleShell>
  );
}
