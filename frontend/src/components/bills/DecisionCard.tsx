import { useState } from "react";
import { EYEBROW_CLASS } from "@/components/settings/styles";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney, isForeignCurrency } from "@/lib/format";
import { ACTOR_LABELS, CATEGORY_LABELS, FIELD_LABELS, VERDICT_LABELS } from "@/lib/labels";
import type {
  BillDecisionView,
  FieldEvidence,
  PaymentCandidate,
  RuleEffect,
  RuleResult,
  Verdict,
} from "@/lib/types";
import { ReviewActions } from "./ReviewActions";

type DecisionCardProps = {
  decision: BillDecisionView;
  onResolved: () => void;
  onSelectEmail: (emailId: string) => void;
};

const CHECKER_RULE_PREFIX = "CHK";
const PERCENT = 100;

const VERDICT_CHIP: Record<Verdict, string> = {
  pay: "bg-success-soft text-success",
  hold: "bg-danger-soft text-danger",
  review: "bg-warning-soft text-warning",
};

const EFFECT_ROW: Record<RuleEffect, { stripe: string; glyph: string; glyphColor: string; label: string }> = {
  hold: { stripe: "border-l-danger", glyph: "✕", glyphColor: "text-danger", label: "Bloquea" },
  review: { stripe: "border-l-warning", glyph: "!", glyphColor: "text-warning", label: "Revisar" },
  pass: { stripe: "border-l-line", glyph: "✓", glyphColor: "text-success", label: "Cumple" },
};

const EFFECT_ORDER: Record<RuleEffect, number> = { hold: 0, review: 1, pass: 2 };

const DISCLOSURE_SUMMARY_CLASS =
  "cursor-pointer list-none rounded text-sm text-muted select-none hover:text-ink focus-visible:outline-2 focus-visible:outline-accent [&::-webkit-details-marker]:hidden";

const DUPLICATE_CHIP = "bg-sunken text-muted";

export function DecisionCard({ decision, onResolved, onSelectEmail }: DecisionCardProps) {
  const policyRules = decision.rule_results.filter((rule) => !isCheckerRule(rule));
  const checkerRules = decision.rule_results.filter(isCheckerRule);
  const failingRules = policyRules
    .filter((rule) => rule.effect !== "pass")
    .sort((first, second) => EFFECT_ORDER[first.effect] - EFFECT_ORDER[second.effect]);
  const passingRules = policyRules.filter((rule) => rule.effect === "pass");

  return (
    <section className="flex flex-col gap-5 rounded-md border border-line bg-panel p-4 md:p-5">
      <VerdictHeader decision={decision} />
      {decision.duplicate_of_bill_id && (
        <DuplicateLink originalBillId={decision.duplicate_of_bill_id} onSelectEmail={onSelectEmail} />
      )}
      {failingRules.length > 0 && (
        <div className="space-y-2">
          <h3 className={EYEBROW_CLASS}>Puntos que impiden pagar solo</h3>
          <RuleList rules={failingRules} />
        </div>
      )}
      {passingRules.length > 0 && (
        <details className="group">
          <summary className={DISCLOSURE_SUMMARY_CLASS}>
            <DisclosureChevron />
            {passingRules.length} reglas cumplidas
          </summary>
          <div className="mt-2">
            <RuleList rules={passingRules} />
          </div>
        </details>
      )}
      {decision.candidate && <EvidenceTable candidate={decision.candidate} />}
      {checkerRules.length > 0 && <CheckerOpinion rules={checkerRules} />}
      <DecisionHistory billId={decision.bill_id} />
      {decision.can_approve && <ReviewActions billId={decision.bill_id} onResolved={onResolved} />}
    </section>
  );
}

function VerdictHeader({ decision }: { decision: BillDecisionView }) {
  const decidedBy = decision.actor === "human" ? "Decisión de una persona" : "Decisión del agente";
  const chipClass = decision.status === "duplicate" ? DUPLICATE_CHIP : VERDICT_CHIP[decision.verdict];
  return (
    <header className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className={EYEBROW_CLASS}>{decidedBy}</p>
        <span
          className={`rounded-full px-3 py-1 text-sm font-medium ${chipClass}`}
        >
          {verdictLabel(decision)}
        </span>
      </div>
      <p className="text-[15px] leading-relaxed text-ink">{decision.explanation}</p>
      {decision.note && (
        <p className="text-sm text-muted">
          Nota: <span className="text-ink">{decision.note}</span>
        </p>
      )}
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 border-t border-line pt-3 text-sm sm:grid-cols-4">
        <Fact label="Beneficiario" value={decision.payee_name} />
        <Fact
          label="Monto"
          value={decision.amount !== null ? formatMoney(decision.amount, decision.currency) : null}
          numeric
        />
        <Fact
          label={isForeignCurrency(decision.currency) ? "≈ USD" : "USD"}
          value={decision.amount_usd !== null ? formatMoney(decision.amount_usd, null) : null}
          numeric
        />
        <Fact label="Categoría" value={decision.category ? CATEGORY_LABELS[decision.category] : null} />
      </dl>
    </header>
  );
}

function DisclosureChevron() {
  return (
    <span aria-hidden className="mr-1.5 inline-block transition-transform group-open:rotate-90">
      ›
    </span>
  );
}

function verdictLabel(decision: BillDecisionView): string {
  if (decision.status === "duplicate") return "Duplicada";
  if (decision.status === "rejected") return "Rechazada";
  return VERDICT_LABELS[decision.verdict];
}

function Fact({ label, value, numeric = false }: { label: string; value: string | null; numeric?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className={`mt-0.5 truncate text-ink ${numeric ? "tabular-nums" : ""}`}>{value ?? "Sin dato"}</dd>
    </div>
  );
}

function RuleList({ rules }: { rules: RuleResult[] }) {
  return (
    <ul className="space-y-1.5">
      {rules.map((rule) => (
        <RuleRow key={rule.rule_id} rule={rule} />
      ))}
    </ul>
  );
}

function RuleRow({ rule }: { rule: RuleResult }) {
  const row = EFFECT_ROW[rule.effect];
  const evidenceEntries = Object.entries(rule.evidence);
  return (
    <li className={`flex gap-3 rounded-sm border-l-2 bg-sunken/60 px-3 py-2 ${row.stripe}`}>
      <span aria-hidden className={`w-3 shrink-0 pt-px text-center text-sm font-medium ${row.glyphColor}`}>
        {row.glyph}
      </span>
      <div className="min-w-0 space-y-0.5">
        <p className="text-sm leading-relaxed text-ink">
          <span className="sr-only">{row.label}: </span>
          {rule.reason}
        </p>
        <p className="text-xs text-muted">
          {rule.rule_id} · {rule.name.replaceAll("_", " ")}
        </p>
        {evidenceEntries.length > 0 && (
          <p className="text-xs break-words text-muted">
            {evidenceEntries.map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`).join(" · ")}
          </p>
        )}
      </div>
    </li>
  );
}

function EvidenceTable({ candidate }: { candidate: PaymentCandidate }) {
  const evidenceByField = new Map<string, FieldEvidence>(
    candidate.evidence.map((evidence) => [evidence.field, evidence]),
  );
  const readFields = Object.entries(FIELD_LABELS).flatMap(([field, label]) => {
    const value = (candidate as Record<string, unknown>)[field];
    if (value === null || value === undefined || value === "") return [];
    const shownValue = field === "amount" ? formatMoney(String(value), null) : String(value);
    return [{ field, label, value: shownValue, evidence: evidenceByField.get(field) }];
  });
  if (readFields.length === 0) return null;
  return (
    <div className="space-y-2">
      <h3 className={EYEBROW_CLASS}>Datos leídos de la factura</h3>
      <dl className="divide-y divide-line rounded-md border border-line">
        {readFields.map((readField) => (
          <div key={readField.field} className="grid gap-1 px-3 py-2 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-3">
            <dt className="text-xs text-muted sm:pt-0.5">{readField.label}</dt>
            <dd className="min-w-0 space-y-1">
              <p className="text-sm break-words text-ink tabular-nums">{readField.value}</p>
              {readField.evidence && (
                <p className="text-xs text-muted">
                  <q className="text-ink/80">{readField.evidence.quote}</q>
                  <span className="ml-2 tabular-nums">
                    confianza {Math.round(readField.evidence.confidence * PERCENT)} %
                  </span>
                </p>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function CheckerOpinion({ rules }: { rules: RuleResult[] }) {
  return (
    <div className="space-y-2">
      <h3 className={EYEBROW_CLASS}>Opinión del verificador (modelo)</h3>
      <p className="text-xs text-muted">
        Un segundo modelo revisa las facturas que pasan las reglas. Solo puede enviar a revisión, nunca aprobar.
      </p>
      <ul className="space-y-1.5">
        {rules.map((rule) => (
          <li key={rule.rule_id} className="flex gap-3 rounded-sm border border-line px-3 py-2">
            <span aria-hidden className={`w-3 shrink-0 text-center text-sm ${EFFECT_ROW[rule.effect].glyphColor}`}>
              {EFFECT_ROW[rule.effect].glyph}
            </span>
            <div className="min-w-0 space-y-0.5">
              {rule.evidence.pregunta && <p className="text-xs text-muted">{rule.evidence.pregunta}</p>}
              <p className="text-sm text-ink">{rule.reason}</p>
              {rule.evidence.probabilidad && (
                <p className="text-xs text-muted tabular-nums">probabilidad {rule.evidence.probabilidad}</p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DuplicateLink({
  originalBillId,
  onSelectEmail,
}: {
  originalBillId: string;
  onSelectEmail: (emailId: string) => void;
}) {
  const [message, setMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function openOriginal() {
    setIsLoading(true);
    setMessage(null);
    try {
      const original = await api.bill(originalBillId);
      const originalEmailId = original.sources.find((source) => source.inbox_email_id)?.inbox_email_id;
      if (originalEmailId) {
        onSelectEmail(originalEmailId);
        return;
      }
      setMessage("La factura original no llegó por correo; está registrada desde el chat o una carga.");
    } catch {
      setMessage("No se pudo abrir la factura original.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="rounded-md border border-line bg-sunken px-3 py-2 text-sm">
      <button
        type="button"
        onClick={openOriginal}
        disabled={isLoading}
        className="rounded font-medium text-accent hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50"
      >
        {isLoading ? "Abriendo..." : "Ver la factura original"}
      </button>
      {message && (
        <p role="alert" className="mt-1 text-muted">
          {message}
        </p>
      )}
    </div>
  );
}

function DecisionHistory({ billId }: { billId: string }) {
  const [history, setHistory] = useState<BillDecisionView[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  function loadHistory(isOpen: boolean) {
    if (!isOpen || history !== null) return;
    api
      .bill(billId)
      .then((detail) => setHistory(detail.history))
      .catch(() => setLoadError(true));
  }

  return (
    <details onToggle={(event) => loadHistory(event.currentTarget.open)} className="group">
      <summary className={DISCLOSURE_SUMMARY_CLASS}>
        <DisclosureChevron />
        Historial de decisiones
      </summary>
      <div className="mt-2" aria-live="polite">
        {loadError && <p className="text-sm text-danger">No se pudo cargar el historial.</p>}
        {!loadError && history === null && (
          <div aria-hidden className="space-y-2">
            <div className="h-3.5 w-2/3 animate-pulse rounded bg-sunken" />
            <div className="h-3.5 w-1/2 animate-pulse rounded bg-sunken" />
          </div>
        )}
        {history && (
          <ol className="space-y-2 border-l border-line pl-3">
            {history.map((entry) => (
              <li key={`${entry.decided_at}-${entry.actor}`} className="text-sm">
                <p className="text-ink">
                  <span className="font-medium">{ACTOR_LABELS[entry.actor]}</span> · {VERDICT_LABELS[entry.verdict]}
                  <span className="ml-2 text-xs text-muted">{formatDateTime(entry.decided_at)}</span>
                </p>
                {entry.note && <p className="text-muted">{entry.note}</p>}
              </li>
            ))}
          </ol>
        )}
      </div>
    </details>
  );
}

function isCheckerRule(rule: RuleResult): boolean {
  return rule.rule_id.startsWith(CHECKER_RULE_PREFIX);
}
