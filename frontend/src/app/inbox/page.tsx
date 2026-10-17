"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ConnectionBar } from "@/components/inbox/ConnectionBar";
import { EmailDetail } from "@/components/inbox/EmailDetail";
import { EmailList, EmailListSkeleton } from "@/components/inbox/EmailList";
import { UnauthorizedError, api, tokenStore } from "@/lib/api";
import type {
  InboxEmailDetail,
  InboxEmailView,
  MailboxConnectionView,
  SimulatedEmailKind,
} from "@/lib/types";
import { PENDING_STATUSES } from "@/lib/types";

const POLL_INTERVAL_MS = 4000;
const IDLE_POLL_INTERVAL_MS = 15000;

const HEADER_LINK_CLASS =
  "flex h-9 items-center rounded-md px-3 text-sm text-muted hover:bg-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-accent";

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
};

async function fetchInboxSnapshot(selectedEmailId: string | null): Promise<InboxSnapshot> {
  const [emails, selectedEmail] = await Promise.all([
    api.emails(),
    selectedEmailId ? api.email(selectedEmailId) : Promise.resolve(null),
  ]);
  return { emails, selectedEmail };
}

export default function InboxPage() {
  const router = useRouter();
  const simulateMenuRef = useRef<HTMLDetailsElement>(null);
  const [connections, setConnections] = useState<MailboxConnectionView[]>([]);
  const [emails, setEmails] = useState<InboxEmailView[] | null>(null);
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

  function logout() {
    tokenStore.clear();
    router.replace("/login");
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 md:px-6">
          <h1 className="text-base font-[450] tracking-[-0.02em] text-ink">Blinka Inbox</h1>
          <div className="flex flex-wrap items-center gap-2">
            <ConnectionBar connections={connections} onUnauthorized={handleUnauthorized} />
            <details ref={simulateMenuRef} className="relative">
              <summary
                aria-disabled={isSimulating}
                className="flex h-9 cursor-pointer list-none items-center rounded-md bg-accent px-3 text-sm font-medium text-white transition-colors select-none hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent [&::-webkit-details-marker]:hidden"
              >
                {isSimulating ? "Simulando..." : "Simular correo"}
              </summary>
              <ul className="absolute left-0 z-10 mt-1 max-h-[70vh] w-72 overflow-y-auto md:right-0 md:left-auto rounded-md border border-line bg-panel py-1 shadow-lg">
                {SIMULATION_OPTIONS.map((option) => (
                  <li key={option.kind}>
                    <button
                      type="button"
                      disabled={isSimulating}
                      onClick={() => simulate(option.kind)}
                      className="block w-full px-3 py-2 text-left text-sm text-ink hover:bg-sunken focus-visible:bg-sunken focus-visible:outline-none disabled:opacity-50"
                    >
                      {option.label}
                    </button>
                  </li>
                ))}
              </ul>
            </details>
            <Link href="/bills" className={HEADER_LINK_CLASS}>
              Cola de revisión
            </Link>
            <Link href="/settings/policy" className={HEADER_LINK_CLASS}>
              Configuración
            </Link>
            <button
              type="button"
              onClick={logout}
              className="h-9 rounded-md px-3 text-sm text-muted hover:bg-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      {loadError && (
        <p role="alert" className="bg-danger-soft px-4 py-2 text-center text-sm text-danger">
          {loadError}
        </p>
      )}

      <main className="mx-auto grid w-full max-w-6xl flex-1 md:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] md:gap-6 md:px-6 md:py-6">
        <section
          aria-label="Correos"
          className={`overflow-hidden bg-panel md:rounded-lg md:border md:border-line ${selectedEmailId ? "hidden md:block" : ""}`}
        >
          <div
            role="group"
            aria-label="Filtrar correos"
            className="flex gap-1.5 border-b border-line px-4 py-2.5"
          >
            <FilterChip
              label="Todos"
              isActive={inboxFilter === "all"}
              onSelect={() => setInboxFilter("all")}
            />
            <FilterChip
              label={`En revisión${reviewCount ? ` (${reviewCount})` : ""}`}
              isActive={isReviewFilter}
              onSelect={() => setInboxFilter("review")}
            />
          </div>
          {visibleEmails === null ? (
            <EmailListSkeleton />
          ) : isReviewQueueEmpty ? (
            <p className="px-5 py-10 text-center text-sm text-muted">
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
          className={`bg-panel md:rounded-lg md:border md:border-line ${selectedEmailId ? "" : "hidden md:block"}`}
        >
          {selectedEmail && selectedEmail.email_id === selectedEmailId ? (
            <EmailDetail
              email={selectedEmail}
              onBack={() => setSelectedEmailId(null)}
              onDecisionChanged={() => setRefreshCount((count) => count + 1)}
              onSelectEmail={setSelectedEmailId}
            />
          ) : (
            <p className="p-7 text-sm text-muted">
              {selectedEmailId
                ? "Cargando correo..."
                : "Selecciona un correo para ver la decisión del agente."}
            </p>
          )}
        </section>
      </main>
    </div>
  );
}

function FilterChip({
  label,
  isActive,
  onSelect,
}: {
  label: string;
  isActive: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={onSelect}
      className={`h-8 rounded-full px-3 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-accent ${isActive ? "bg-accent-wash text-accent" : "text-muted hover:bg-sunken hover:text-ink"}`}
    >
      {label}
    </button>
  );
}
