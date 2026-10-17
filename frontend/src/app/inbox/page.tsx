"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ConsoleShell, ConsoleTopBar } from "@/components/console/ConsoleShell";
import { ConnectionBar } from "@/components/inbox/ConnectionBar";
import { EmailDetail } from "@/components/inbox/EmailDetail";
import { EmailList, EmailListSkeleton } from "@/components/inbox/EmailList";
import { InboxMetrics } from "@/components/inbox/InboxMetrics";
import { PRIMARY_BUTTON_CLASS } from "@/components/settings/styles";
import { UnauthorizedError, api, tokenStore } from "@/lib/api";
import type {
  BudgetUsageView,
  InboxEmailDetail,
  InboxEmailView,
  MailboxConnectionView,
  SimulatedEmailKind,
} from "@/lib/types";
import { PENDING_STATUSES } from "@/lib/types";

const POLL_INTERVAL_MS = 4000;
const IDLE_POLL_INTERVAL_MS = 15000;

const SIMULATION_OPTIONS: { kind: SimulatedEmailKind; label: string }[] = [
  { kind: "invoice_usd", label: "Factura normal de ACME (USD)" },
  { kind: "invoice_usd_pdf", label: "La misma factura de ACME en PDF" },
  { kind: "aws_card", label: "Factura de AWS con tarjeta registrada" },
  { kind: "person_cuenta_cobro", label: "Cuenta de cobro de una contratista" },
  { kind: "person_cuenta_cobro_second", label: "Segunda cuenta de cobro del mes" },
  { kind: "aws_impersonation", label: "Suplantación de AWS (cuenta personal)" },
  { kind: "amaz0n_blacklisted", label: "Dominio en lista negra" },
  { kind: "over_auto_pay", label: "Supera tope de autopago" },
  { kind: "over_hard_cap", label: "Supera tope por pago" },
  { kind: "agreement_mismatch", label: "No cuadra con lo acordado" },
  { kind: "unknown_payee", label: "Beneficiario no registrado" },
  { kind: "no_currency", label: "Sin moneda explícita" },
  { kind: "invoice_clp", label: "Factura con remitente desconocido" },
  { kind: "prompt_injection", label: "Intento de prompt injection" },
  { kind: "plain", label: "Correo sin factura" },
];

type InboxFilter = "all" | "review";

type InboxSnapshot = {
  emails: InboxEmailView[];
  selectedEmail: InboxEmailDetail | null;
  budgets: BudgetUsageView[];
};

async function fetchInboxSnapshot(selectedEmailId: string | null): Promise<InboxSnapshot> {
  const [emails, selectedEmail, budgets] = await Promise.all([
    api.emails(),
    selectedEmailId ? api.email(selectedEmailId) : Promise.resolve(null),
    api.budgets(),
  ]);
  return { emails, selectedEmail, budgets };
}

export default function InboxPage() {
  const router = useRouter();
  const simulateMenuRef = useRef<HTMLDetailsElement>(null);
  const [connections, setConnections] = useState<MailboxConnectionView[]>([]);
  const [emails, setEmails] = useState<InboxEmailView[] | null>(null);
  const [budgets, setBudgets] = useState<BudgetUsageView[] | null>(null);
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const [selectedEmail, setSelectedEmail] = useState<InboxEmailDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [inboxFilter, setInboxFilter] = useState<InboxFilter>("all");
  const [refreshCount, setRefreshCount] = useState(0);
  const reviewEmails = (emails ?? []).filter((email) => email.status === "review");
  const isReviewFilter = inboxFilter === "review";
  const visibleEmails = emails && isReviewFilter ? reviewEmails : emails;
  const reviewCount = reviewEmails.length;
  const hasPendingEmails = (emails ?? []).some((email) => PENDING_STATUSES.has(email.status));
  const isReviewQueueEmpty = isReviewFilter && visibleEmails?.length === 0;
  const caption = emails
    ? `${emails.length} correos · ${reviewCount} en revisión`
    : "Cargando correos...";

  const handleUnauthorized = useCallback(
    (error: unknown): boolean => {
      if (!(error instanceof UnauthorizedError)) return false;
      router.replace("/login");
      return true;
    },
    [router],
  );

  useEffect(() => {
    if (!tokenStore.get()) {
      router.replace("/login");
      return;
    }
    api
      .connections()
      .then(setConnections)
      .catch((error: unknown) => handleUnauthorized(error));
  }, [router, handleUnauthorized]);

  useEffect(() => {
    if (!tokenStore.get()) return;
    let isCancelled = false;
    let isLoading = false;
    const loadInbox = () => {
      if (isLoading) return;
      isLoading = true;
      fetchInboxSnapshot(selectedEmailId)
        .then((snapshot) => {
          if (isCancelled) return;
          setEmails(snapshot.emails);
          setSelectedEmail(snapshot.selectedEmail);
          setBudgets(snapshot.budgets);
          setLoadError(null);
        })
        .catch((error: unknown) => {
          if (isCancelled || handleUnauthorized(error)) return;
          setLoadError("No se pudo cargar la bandeja. Reintentando...");
        })
        .finally(() => {
          isLoading = false;
        });
    };
    loadInbox();
    const pollIntervalMs = hasPendingEmails ? POLL_INTERVAL_MS : IDLE_POLL_INTERVAL_MS;
    const pollTimer = setInterval(loadInbox, pollIntervalMs);
    return () => {
      isCancelled = true;
      clearInterval(pollTimer);
    };
  }, [selectedEmailId, hasPendingEmails, handleUnauthorized, refreshCount]);

  async function simulate(kind: SimulatedEmailKind) {
    if (simulateMenuRef.current) simulateMenuRef.current.open = false;
    setIsSimulating(true);
    try {
      const simulatedEmail = await api.simulate(kind);
      setSelectedEmailId(simulatedEmail.email_id);
    } catch (error) {
      if (!handleUnauthorized(error)) setLoadError("No se pudo simular el correo.");
    } finally {
      setIsSimulating(false);
    }
  }

  return (
    <ConsoleShell>
      <ConsoleTopBar
        title="Bandeja"
        caption={caption}
        actions={
          <>
            <ConnectionBar connections={connections} onUnauthorized={handleUnauthorized} />
            <details ref={simulateMenuRef} className="relative">
              <summary
                aria-disabled={isSimulating}
                className={`${PRIMARY_BUTTON_CLASS} h-9 cursor-pointer list-none px-4 select-none [&::-webkit-details-marker]:hidden`}
              >
                {isSimulating ? "Simulando..." : "Simular correo"}
              </summary>
              <ul className="absolute left-0 z-10 mt-1 max-h-[70vh] w-72 overflow-y-auto rounded border border-line bg-panel py-1 md:right-0 md:left-auto">
                {SIMULATION_OPTIONS.map((option) => (
                  <li key={option.kind}>
                    <button
                      type="button"
                      disabled={isSimulating}
                      onClick={() => simulate(option.kind)}
                      className="block w-full px-4 py-2 text-left text-sm text-ink hover:bg-sunken focus-visible:bg-sunken focus-visible:outline-none disabled:opacity-50"
                    >
                      {option.label}
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          </>
        }
      />

      {loadError && (
        <p role="alert" className="border-b border-line bg-danger-soft px-4 py-2 text-sm text-danger md:px-8">
          <span aria-hidden>✕ </span>
          {loadError}
        </p>
      )}

      <InboxMetrics emails={emails} budgets={budgets} />

      <div className="flex flex-1 flex-col gap-4 px-4 py-6 md:px-8">
        <div role="group" aria-label="Filtrar correos" className="flex gap-1">
          <FilterTab label="Todos" isActive={inboxFilter === "all"} onSelect={() => setInboxFilter("all")} />
          <FilterTab
            label="En revisión"
            count={reviewCount}
            isActive={isReviewFilter}
            onSelect={() => setInboxFilter("review")}
          />
        </div>
        <main className="grid flex-1 items-start gap-8 md:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] xl:grid-cols-[minmax(0,1fr)_minmax(0,34rem)]">
          <section
            aria-label="Correos"
            className={`overflow-hidden rounded-lg border border-line bg-panel ${selectedEmailId ? "hidden md:block" : ""}`}
          >
            {visibleEmails === null ? (
              <EmailListSkeleton />
            ) : isReviewQueueEmpty ? (
              <p className="px-6 py-12 text-sm text-muted">
                No hay facturas esperando una decisión.
              </p>
            ) : (
              <EmailList
                emails={visibleEmails}
                selectedEmailId={selectedEmailId}
                onSelect={setSelectedEmailId}
              />
            )}
          </section>
          <section
            aria-label="Detalle del correo"
            className={selectedEmailId ? "" : "hidden md:block"}
          >
            {selectedEmail && selectedEmail.email_id === selectedEmailId ? (
              <EmailDetail
                email={selectedEmail}
                onBack={() => setSelectedEmailId(null)}
                onDecisionChanged={() => setRefreshCount((count) => count + 1)}
                onSelectEmail={setSelectedEmailId}
              />
            ) : (
              <p className="py-4 text-sm text-muted">
                {selectedEmailId
                  ? "Cargando correo..."
                  : "Selecciona un correo para ver la decisión del agente."}
              </p>
            )}
          </section>
        </main>
      </div>
    </ConsoleShell>
  );
}

function FilterTab({
  label,
  count,
  isActive,
  onSelect,
}: {
  label: string;
  count?: number;
  isActive: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={onSelect}
      className={`min-h-10 rounded px-3 text-sm font-normal transition-colors focus-visible:outline-2 focus-visible:outline-accent ${isActive ? "bg-accent-wash text-accent" : "text-ink hover:bg-sunken"}`}
    >
      {label}
      {count ? <span className="ml-2 text-accent">{count}</span> : null}
    </button>
  );
}
