import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { EXTRACTION_METHOD_LABELS, RUN_STEP_LABELS, VERDICT_LABELS } from "@/lib/labels";
import type { PaymentRunEvent, PaymentRunStatus, RunStatus, Verdict } from "@/lib/types";

const RUN_POLL_INTERVAL_MS = 3000;
const UNFINISHED_RUN_STATUSES: ReadonlySet<RunStatus> = new Set(["pending", "running"]);
const EXPECTED_STEPS = ["started", "classified", "extracted", "claimed", "decided", "completed"];
const BUYER_ISSUED = "buyer";
const TERMINAL_DETOUR_STEPS: ReadonlySet<string> = new Set(["not_a_bill", "extraction_failed"]);

export function RunTimeline({ runId }: { runId: string }) {
  const [run, setRun] = useState<PaymentRunStatus | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    let isActive = true;
    let pollTimer: number | undefined;
    async function poll() {
      try {
        const latestRun = await api.runStatus(runId);
        if (!isActive) return;
        setRun(latestRun);
        setLoadError(false);
        if (UNFINISHED_RUN_STATUSES.has(latestRun.status)) {
          pollTimer = window.setTimeout(poll, RUN_POLL_INTERVAL_MS);
        }
      } catch {
        if (!isActive) return;
        setLoadError(true);
        pollTimer = window.setTimeout(poll, RUN_POLL_INTERVAL_MS);
      }
    }
    poll();
    return () => {
      isActive = false;
      window.clearTimeout(pollTimer);
    };
  }, [runId]);

  if (loadError && run === null) {
    return <p className="text-xs text-muted">No se pudo cargar el avance del agente.</p>;
  }
  if (run === null) {
    return (
      <div aria-hidden className="space-y-2 border-l border-line pl-4">
        <div className="h-3.5 w-1/3 animate-pulse rounded bg-sunken" />
        <div className="h-3.5 w-1/4 animate-pulse rounded bg-sunken" />
      </div>
    );
  }
  const isUnfinished = UNFINISHED_RUN_STATUSES.has(run.status);
  const upcomingSteps = isUnfinished ? pendingSteps(run.events) : [];
  return (
    <ol aria-label="Pasos del agente" className="space-y-2 border-l border-line pl-4">
      {run.events.map((event, index) => {
        const isLatest = index === run.events.length - 1;
        const hint = stepHint(event);
        return (
          <li key={`${event.step}-${event.created_at}`} className="text-sm">
            <p className="text-ink">
              <span aria-hidden className={`mr-2 text-accent ${isLatest && isUnfinished ? "animate-pulse" : ""}`}>
                ✓
              </span>
              {RUN_STEP_LABELS[event.step] ?? event.step}
              <span className="ml-2 text-xs text-muted">{formatRelative(event.created_at)}</span>
            </p>
            {hint && <p className="ml-6 text-xs text-muted">{hint}</p>}
          </li>
        );
      })}
      {upcomingSteps.map((step) => (
        <li key={step} className="text-sm text-quiet">
          <span aria-hidden className="mr-2">
            ·
          </span>
          {RUN_STEP_LABELS[step]}
        </li>
      ))}
    </ol>
  );
}

function pendingSteps(events: PaymentRunEvent[]): string[] {
  const seenSteps = new Set(events.map((event) => event.step));
  const tookDetour = events.some((event) => TERMINAL_DETOUR_STEPS.has(event.step));
  if (tookDetour) return seenSteps.has("completed") ? [] : ["completed"];
  return EXPECTED_STEPS.filter((step) => !seenSteps.has(step));
}

function stepHint(event: PaymentRunEvent): string | null {
  const { payload } = event;
  if (event.step === "decided" && typeof payload.verdict === "string") {
    return VERDICT_LABELS[payload.verdict as Verdict] ?? null;
  }
  if (event.step === "extracted" && typeof payload.method === "string") {
    const methodLabel = EXTRACTION_METHOD_LABELS[payload.method];
    const originLabel = documentOriginLabel(payload.document_origin);
    const sourceLabels = [methodLabel && `Leído desde ${methodLabel}`, originLabel].filter(Boolean);
    return sourceLabels.length ? sourceLabels.join(" · ") : null;
  }
  if (event.step === "not_a_bill" && typeof payload.reason === "string") {
    return payload.reason;
  }
  return null;
}

function documentOriginLabel(documentOrigin: unknown): string | null {
  if (!documentOrigin || typeof documentOrigin !== "object") return null;
  const { standard, authority, country, issued_by } = documentOrigin as Record<string, unknown>;
  if (typeof standard !== "string" || typeof country !== "string") return null;
  const authoritySuffix = typeof authority === "string" ? ` (${authority})` : "";
  const issuerSuffix = issued_by === BUYER_ISSUED ? ", emitido por el comprador" : "";
  return `${standard}${authoritySuffix}, origen ${country}${issuerSuffix}`;
}
