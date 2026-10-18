import { useEffect, useRef, useState } from "react";
import { DANGER_TEXT_BUTTON_CLASS, SECTION_HEADING_CLASS } from "@/components/settings/styles";
import { ApiError, HTTP_CONFLICT, api } from "@/lib/api";
import type { DemoCatalogView, DemoSectionView } from "@/lib/types";
import { useDemoLaunches } from "@/lib/useDemoLaunches";
import { ResetDemoDialog } from "./ResetDemoDialog";
import { ScenarioRow } from "./ScenarioRow";
import { SelfSendCard } from "./SelfSendCard";

const OPEN_BY_DEFAULT_SECTION = "happy_path";
const HTTP_TOO_MANY_REQUESTS = 429;
const SECURITY_SECTION = "security";
const MALWARE_SCENARIO_ID = "security_malware";
const MALWARE_SCAN_OFF_HINT = "Enable the malware scan to run this case.";
const DISCLOSURE_SUMMARY_CLASS =
  "flex cursor-pointer list-none items-center gap-2 rounded py-3 text-sm font-normal text-ink select-none focus-visible:outline-2 focus-visible:outline-accent [&::-webkit-details-marker]:hidden";

type DemoScenariosPanelProps = {
  catalog: DemoCatalogView;
  isOpen: boolean;
  onClose: () => void;
  onLaunched: () => void;
  onReset: () => void;
};

export function DemoScenariosPanel({ catalog, isOpen, onClose, onLaunched, onReset }: DemoScenariosPanelProps) {
  const panelRef = useRef<HTMLDialogElement>(null);
  const { launches, track, clear } = useDemoLaunches(onLaunched);
  const [isResetDialogOpen, setIsResetDialogOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [panelError, setPanelError] = useState<string | null>(null);

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    if (isOpen && !panel.open) panel.showModal();
    if (!isOpen && panel.open) panel.close();
  }, [isOpen]);

  async function send(scenarioId: string) {
    setPanelError(null);
    setStatusMessage(null);
    try {
      track(await api.launchScenario(scenarioId));
      onLaunched();
    } catch (error) {
      setPanelError(launchErrorMessage(error));
    }
  }

  async function download(scenarioId: string) {
    setPanelError(null);
    try {
      await api.downloadScenarioKit(scenarioId);
    } catch {
      setPanelError("The scenario files could not be downloaded.");
    }
  }

  async function reset() {
    setIsResetting(true);
    setPanelError(null);
    try {
      const resetResult = await api.resetDemo();
      clear();
      setStatusMessage(`Demo restored: ${resetResult.seeded_bills} historical bills loaded.`);
      setIsResetDialogOpen(false);
      onReset();
    } catch (error) {
      setPanelError(isBusyError(error) ? "Demo is busy, try again in a moment." : "The demo could not be reset.");
      setIsResetDialogOpen(false);
    } finally {
      setIsResetting(false);
    }
  }

  return (
    <dialog
      ref={panelRef}
      onClose={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      aria-labelledby="demo-panel-title"
      className="m-0 ml-auto h-dvh max-h-none w-full max-w-none border-l border-line bg-panel p-0 text-ink backdrop:bg-night/20 sm:w-[420px]"
    >
      <div className="flex h-full flex-col">
        <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-5">
          <div className="flex flex-col gap-1">
            <h2 id="demo-panel-title" className={SECTION_HEADING_CLASS}>
              Demo scenarios
            </h2>
            <p className="text-xs text-muted">{catalog.company_name}</p>
            <p className="text-xs text-muted">
              Guardrail {catalog.is_guardrail_enforced ? "on" : "off"} · Malware scan{" "}
              {catalog.is_malware_scan_enabled ? "on" : "off"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close demo scenarios"
            className="flex size-10 items-center justify-center rounded text-muted hover:bg-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
          >
            ✕
          </button>
        </header>
        <div className="flex flex-1 flex-col gap-2 overflow-y-auto px-6 py-4">
          {statusMessage && (
            <p role="status" className="rounded bg-accent-wash px-3 py-2 text-sm text-accent">
              {statusMessage}
            </p>
          )}
          {panelError && (
            <p role="alert" className="text-sm text-danger">
              <span aria-hidden>✕ </span>
              {panelError}
            </p>
          )}
          {catalog.sections.map((section) => (
            <ScenarioSection
              key={section.section}
              section={section}
              catalog={catalog}
              launches={launches}
              isResetting={isResetting}
              onSend={send}
              onDownload={download}
            />
          ))}
          <SelfSendCard destinations={catalog.destinations} />
          <div className="flex flex-col gap-1 border-t border-line pt-6 pb-2">
            <button
              type="button"
              onClick={() => setIsResetDialogOpen(true)}
              disabled={isResetting}
              className={`${DANGER_TEXT_BUTTON_CLASS} self-start`}
            >
              {isResetting ? "Resetting…" : "Reset demo"}
            </button>
            <p className="text-xs text-muted">
              Restores the initial data. Reset before a demo to start from a clean month.
            </p>
          </div>
        </div>
      </div>
      <ResetDemoDialog
        isOpen={isResetDialogOpen}
        isResetting={isResetting}
        onCancel={() => setIsResetDialogOpen(false)}
        onConfirm={reset}
      />
    </dialog>
  );
}

function ScenarioSection({
  section,
  catalog,
  launches,
  isResetting,
  onSend,
  onDownload,
}: {
  section: DemoSectionView;
  catalog: DemoCatalogView;
  launches: ReturnType<typeof useDemoLaunches>["launches"];
  isResetting: boolean;
  onSend: (scenarioId: string) => void;
  onDownload: (scenarioId: string) => void;
}) {
  const isSecurity = section.section === SECURITY_SECTION;
  return (
    <details open={section.section === OPEN_BY_DEFAULT_SECTION} className="group border-t border-line first:border-t-0">
      <summary className={DISCLOSURE_SUMMARY_CLASS}>
        <span aria-hidden className="inline-block text-muted transition-transform group-open:rotate-90">
          ›
        </span>
        {section.title}
        <span className="text-muted">({section.scenarios.length})</span>
      </summary>
      {isSecurity && !catalog.is_guardrail_enforced && (
        <p className="pb-2 text-xs text-muted">
          Guardrail is off: injection cases will be held by rule R02 instead of blocked.
        </p>
      )}
      <ul className="flex flex-col">
        {section.scenarios.map((scenario) => {
          const isMalwareBlocked = scenario.scenario_id === MALWARE_SCENARIO_ID && !catalog.is_malware_scan_enabled;
          return (
            <ScenarioRow
              key={scenario.scenario_id}
              scenario={scenario}
              launch={launches[scenario.scenario_id]}
              isSendDisabled={isResetting || isMalwareBlocked}
              disabledHint={isMalwareBlocked ? MALWARE_SCAN_OFF_HINT : null}
              onSend={onSend}
              onDownload={onDownload}
            />
          );
        })}
      </ul>
    </details>
  );
}

function launchErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === HTTP_TOO_MANY_REQUESTS) {
    return "Several scenarios are already running. Wait for one to finish.";
  }
  if (isBusyError(error)) return "Demo is busy, try again in a moment.";
  return "The scenario could not be sent.";
}

function isBusyError(error: unknown): boolean {
  return error instanceof ApiError && error.status === HTTP_CONFLICT;
}
