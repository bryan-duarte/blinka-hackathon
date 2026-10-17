"use client";

import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { type ReportError, useReportError } from "@/components/settings/errors";
import {
  CARD_CLASS,
  DANGER_TEXT_BUTTON_CLASS,
  EYEBROW_CLASS,
  HINT_CLASS,
  INPUT_CLASS,
  LABEL_CLASS,
  PRIMARY_BUTTON_CLASS,
  QUIET_BUTTON_CLASS,
  SECONDARY_BUTTON_CLASS,
  SECTION_HEADING_CLASS,
} from "@/components/settings/styles";
import { api } from "@/lib/api";
import { CURRENCY_CODE_LENGTH, USD_CURRENCY, formatMoney } from "@/lib/format";
import {
  CATEGORY_LABELS,
  IDENTIFIER_KINDS,
  IDENTIFIER_KIND_LABELS,
  PAYEE_KIND_GROUP_LABELS,
  PAYEE_KIND_LABELS,
  PAYEE_STATUS_LABELS,
  PAYMENT_CATEGORIES,
  PAYMENT_METHOD_LABELS,
} from "@/lib/labels";
import type {
  IdentifierKind,
  PayeeFields,
  PayeeKind,
  PayeeStatus,
  PayeeView,
  PaymentCategory,
  PaymentMethod,
} from "@/lib/types";

const PAYEE_KINDS: PayeeKind[] = ["service", "company", "person"];
const PAYMENT_METHODS = Object.keys(PAYMENT_METHOD_LABELS) as PaymentMethod[];
const PAYEE_STATUSES = Object.keys(PAYEE_STATUS_LABELS) as PayeeStatus[];
const IDENTIFIER_TAKEN_MESSAGE = "Este identificador ya pertenece a otro beneficiario.";
const PAYEE_CHANGED_MESSAGE = "Alguien modificó este beneficiario; recarga para ver los cambios.";
const PAYEE_IN_USE_MESSAGE = "Tiene facturas registradas. Bloquéalo en vez de eliminarlo.";

type PayeeDraft = Record<
  | "display_name"
  | "currency"
  | "per_payment_max_usd"
  | "monthly_budget_usd"
  | "agreed_amount_usd"
  | "agreed_tolerance_pct",
  string
> & {
  kind: PayeeKind;
  status: PayeeStatus;
  payment_method: PaymentMethod;
  default_category: PaymentCategory | "";
};

const EMPTY_DRAFT: PayeeDraft = {
  kind: "service",
  display_name: "",
  status: "allowed",
  payment_method: "bank_transfer",
  default_category: "",
  currency: USD_CURRENCY,
  per_payment_max_usd: "",
  monthly_budget_usd: "",
  agreed_amount_usd: "",
  agreed_tolerance_pct: "",
};

function toDraft(payee: PayeeView): PayeeDraft {
  return {
    kind: payee.kind,
    display_name: payee.display_name,
    status: payee.status,
    payment_method: payee.payment_method,
    default_category: payee.default_category ?? "",
    currency: payee.currency,
    per_payment_max_usd: payee.per_payment_max_usd ?? "",
    monthly_budget_usd: payee.monthly_budget_usd ?? "",
    agreed_amount_usd: payee.agreed_amount_usd ?? "",
    agreed_tolerance_pct: payee.agreed_tolerance_pct ?? "",
  };
}

function optionalAmount(value: string): string | null {
  return value.trim() === "" ? null : value.trim();
}

function toEditableFields(draft: PayeeDraft): Omit<PayeeFields, "kind"> {
  return {
    display_name: draft.display_name.trim(),
    status: draft.status,
    payment_method: draft.payment_method,
    default_category: draft.default_category || null,
    currency: draft.currency.trim().toUpperCase(),
    per_payment_max_usd: optionalAmount(draft.per_payment_max_usd),
    monthly_budget_usd: optionalAmount(draft.monthly_budget_usd),
    agreed_amount_usd: optionalAmount(draft.agreed_amount_usd),
    agreed_tolerance_pct: optionalAmount(draft.agreed_tolerance_pct),
  };
}

export default function PayeesPage() {
  const reportError = useReportError();
  const [payees, setPayees] = useState<PayeeView[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editingPayee, setEditingPayee] = useState<PayeeView | "new" | null>(null);

  const loadPayees = useCallback(() => {
    api
      .payees()
      .then((loadedPayees) => {
        setPayees(loadedPayees);
        setLoadError(null);
      })
      .catch((error: unknown) =>
        setLoadError(reportError(error, "", "No se pudieron cargar los beneficiarios.")),
      );
  }, [reportError]);

  useEffect(loadPayees, [loadPayees]);

  function replacePayee(updatedPayee: PayeeView) {
    setPayees((current) =>
      current?.map((payee) => (payee.payee_id === updatedPayee.payee_id ? updatedPayee : payee)) ?? null,
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className={SECTION_HEADING_CLASS}>Beneficiarios registrados</h2>
          <p className={`${HINT_CLASS} mt-1 max-w-xl`}>
            El agente reconoce a quién paga por sus identificadores (cuenta, RUT, dominio), no por el nombre. Una
            factura con un nombre conocido y una cuenta distinta se frena.
          </p>
        </div>
        <button type="button" onClick={() => setEditingPayee("new")} className={PRIMARY_BUTTON_CLASS}>
          Nuevo beneficiario
        </button>
      </div>

      {loadError && (
        <p role="alert" className="text-sm text-danger">
          {loadError}
        </p>
      )}
      {payees === null && !loadError && <PayeesSkeleton />}
      {payees?.length === 0 && (
        <p className={`${CARD_CLASS} p-5 text-sm text-muted`}>
          Aún no hay beneficiarios. Crea uno o ejecuta el script de semilla para cargar la empresa de demo.
        </p>
      )}
      {payees &&
        PAYEE_KINDS.map((kind) => {
          const payeesOfKind = payees.filter((payee) => payee.kind === kind);
          if (payeesOfKind.length === 0) return null;
          return (
            <section key={kind} className="space-y-3" aria-label={PAYEE_KIND_GROUP_LABELS[kind]}>
              <h3 className={EYEBROW_CLASS}>
                {PAYEE_KIND_GROUP_LABELS[kind]}
              </h3>
              <ul className="grid gap-3 md:grid-cols-2">
                {payeesOfKind.map((payee) => (
                  <PayeeCard
                    key={payee.payee_id}
                    payee={payee}
                    onEdit={() => setEditingPayee(payee)}
                    onChanged={replacePayee}
                    onDeleted={loadPayees}
                    reportError={reportError}
                  />
                ))}
              </ul>
            </section>
          );
        })}

      {editingPayee && (
        <PayeeDialog
          payee={editingPayee === "new" ? null : editingPayee}
          onClose={() => setEditingPayee(null)}
          onSaved={() => {
            setEditingPayee(null);
            loadPayees();
          }}
          reportError={reportError}
        />
      )}
    </div>
  );
}

function PayeeCard({
  payee,
  onEdit,
  onChanged,
  onDeleted,
  reportError,
}: {
  payee: PayeeView;
  onEdit: () => void;
  onChanged: (payee: PayeeView) => void;
  onDeleted: () => void;
  reportError: ReportError;
}) {
  const [cardError, setCardError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const isBlocked = payee.status === "blacklisted";

  async function deletePayee() {
    if (!window.confirm(`¿Eliminar a ${payee.display_name}?`)) return;
    setIsDeleting(true);
    setCardError(null);
    try {
      await api.deletePayee(payee.payee_id);
      onDeleted();
    } catch (error) {
      setCardError(reportError(error, PAYEE_IN_USE_MESSAGE, "No se pudo eliminar."));
      setIsDeleting(false);
    }
  }

  return (
    <li className={`${CARD_CLASS} flex flex-col gap-4 p-4`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[15px] font-medium text-ink">{payee.display_name}</p>
          <p className={HINT_CLASS}>
            {PAYEE_KIND_LABELS[payee.kind]} · {PAYMENT_METHOD_LABELS[payee.payment_method]}
            {payee.default_category && ` · ${CATEGORY_LABELS[payee.default_category]}`}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${isBlocked ? "bg-danger-soft text-danger" : "bg-success-soft text-success"}`}
        >
          {PAYEE_STATUS_LABELS[payee.status]}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <Limit label="Máximo por pago" value={payee.per_payment_max_usd} />
        <Limit label="Presupuesto mensual" value={payee.monthly_budget_usd} />
        <Limit
          label="Monto acordado"
          value={payee.agreed_amount_usd}
          suffix={payee.agreed_tolerance_pct ? `± ${Number(payee.agreed_tolerance_pct)} %` : undefined}
        />
        <div>
          <dt className="text-xs text-muted">Moneda de cobro</dt>
          <dd className="text-ink">{payee.currency}</dd>
        </div>
      </dl>
      <IdentifierManager payee={payee} onChanged={onChanged} reportError={reportError} />
      {cardError && (
        <p role="alert" className="text-sm text-danger">
          {cardError}
        </p>
      )}
      <div className="flex gap-3 border-t border-line pt-3">
        <button type="button" onClick={onEdit} className={QUIET_BUTTON_CLASS}>
          Editar
        </button>
        <button type="button" onClick={deletePayee} disabled={isDeleting} className={DANGER_TEXT_BUTTON_CLASS}>
          {isDeleting ? "Eliminando..." : "Eliminar"}
        </button>
      </div>
    </li>
  );
}

function Limit({ label, value, suffix }: { label: string; value: string | null; suffix?: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-ink tabular-nums">
        {value !== null ? formatMoney(value, USD_CURRENCY) : <span className="text-muted">Sin tope</span>}
        {value !== null && suffix && <span className="ml-1 text-xs text-muted">{suffix}</span>}
      </dd>
    </div>
  );
}

function IdentifierManager({
  payee,
  onChanged,
  reportError,
}: {
  payee: PayeeView;
  onChanged: (payee: PayeeView) => void;
  reportError: ReportError;
}) {
  const [kind, setKind] = useState<IdentifierKind>("bank_account");
  const [value, setValue] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [identifierError, setIdentifierError] = useState<string | null>(null);
  const fieldId = `identifier-${payee.payee_id}`;

  async function addIdentifier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!value.trim()) return;
    setIsSaving(true);
    setIdentifierError(null);
    try {
      onChanged(await api.addIdentifier(payee.payee_id, { kind, value: value.trim() }));
      setValue("");
    } catch (error) {
      setIdentifierError(reportError(error, IDENTIFIER_TAKEN_MESSAGE, "No se pudo agregar."));
    } finally {
      setIsSaving(false);
    }
  }

  async function deleteIdentifier(identifierId: string) {
    setIdentifierError(null);
    try {
      await api.deleteIdentifier(payee.payee_id, identifierId);
      onChanged({
        ...payee,
        identifiers: payee.identifiers.filter((identifier) => identifier.identifier_id !== identifierId),
      });
    } catch (error) {
      setIdentifierError(reportError(error, "", "No se pudo quitar el identificador."));
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-ink">Identificadores</p>
      {payee.identifiers.length === 0 ? (
        <p className={HINT_CLASS}>Sin identificadores: solo coincidirá por nombre y pasará a revisión.</p>
      ) : (
        <ul className="divide-y divide-line rounded-md border border-line">
          {payee.identifiers.map((identifier) => (
            <li key={identifier.identifier_id} className="flex items-center justify-between gap-3 px-3 py-1.5">
              <div className="min-w-0">
                <p className="text-xs text-muted">{IDENTIFIER_KIND_LABELS[identifier.kind]}</p>
                <p className="truncate text-sm text-ink tabular-nums">{identifier.raw_value}</p>
              </div>
              <button
                type="button"
                aria-label={`Quitar ${identifier.raw_value}`}
                onClick={() => deleteIdentifier(identifier.identifier_id)}
                className="grid size-8 shrink-0 place-items-center rounded text-muted hover:bg-sunken hover:text-danger focus-visible:outline-2 focus-visible:outline-accent"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={addIdentifier} className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor={`${fieldId}-kind`} className="sr-only">
          Tipo de identificador
        </label>
        <select
          id={`${fieldId}-kind`}
          value={kind}
          onChange={(event) => setKind(event.target.value as IdentifierKind)}
          className={`${INPUT_CLASS} sm:w-44`}
        >
          {IDENTIFIER_KINDS.map((identifierKind) => (
            <option key={identifierKind} value={identifierKind}>
              {IDENTIFIER_KIND_LABELS[identifierKind]}
            </option>
          ))}
        </select>
        <label htmlFor={`${fieldId}-value`} className="sr-only">
          Valor del identificador
        </label>
        <input
          id={`${fieldId}-value`}
          value={value}
          placeholder="Valor"
          onChange={(event) => setValue(event.target.value)}
          className={INPUT_CLASS}
        />
        <button type="submit" disabled={isSaving || !value.trim()} className={SECONDARY_BUTTON_CLASS}>
          {isSaving ? "Agregando..." : "Agregar"}
        </button>
      </form>
      {identifierError && (
        <p role="alert" className="text-sm text-danger">
          {identifierError}
        </p>
      )}
    </div>
  );
}

function PayeeDialog({
  payee,
  onClose,
  onSaved,
  reportError,
}: {
  payee: PayeeView | null;
  onClose: () => void;
  onSaved: () => void;
  reportError: ReportError;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState<PayeeDraft>(payee ? toDraft(payee) : EMPTY_DRAFT);
  const [isSaving, setIsSaving] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const isNew = payee === null;

  useEffect(() => {
    dialogRef.current?.showModal();
  }, []);

  function update(changes: Partial<PayeeDraft>) {
    setDraft((current) => ({ ...current, ...changes }));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = toEditableFields(draft);
    const amounts = [
      fields.per_payment_max_usd,
      fields.monthly_budget_usd,
      fields.agreed_amount_usd,
      fields.agreed_tolerance_pct,
    ];
    const hasInvalidAmount = amounts.some((amount) => amount !== null && !(Number(amount) >= 0));
    if (hasInvalidAmount) {
      setDialogError("Los montos deben ser números mayores o iguales a 0.");
      return;
    }
    setIsSaving(true);
    setDialogError(null);
    try {
      if (payee === null) {
        await api.createPayee({ ...fields, kind: draft.kind, identifiers: [] });
      } else {
        await api.updatePayee(payee.payee_id, { ...fields, version: payee.version });
      }
      onSaved();
    } catch (error) {
      const conflictMessage = isNew ? "Ya existe un beneficiario con ese nombre." : PAYEE_CHANGED_MESSAGE;
      setDialogError(reportError(error, conflictMessage, "No se pudo guardar. Revisa los datos."));
      setIsSaving(false);
    }
  }

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-labelledby="payee-dialog-title"
      className="m-auto w-[min(36rem,calc(100vw-2rem))] rounded-lg border border-line bg-panel p-0 text-ink backdrop:bg-ink/30"
    >
      <form onSubmit={save} className="space-y-4 p-5">
        <h2 id="payee-dialog-title" className={SECTION_HEADING_CLASS}>
          {isNew ? "Nuevo beneficiario" : `Editar ${payee.display_name}`}
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="payee-name" label="Nombre" className="sm:col-span-2">
            <input
              id="payee-name"
              required
              value={draft.display_name}
              onChange={(event) => update({ display_name: event.target.value })}
              className={INPUT_CLASS}
            />
          </Field>
          <Field id="payee-kind" label="Tipo">
            <select
              id="payee-kind"
              value={draft.kind}
              disabled={!isNew}
              onChange={(event) => update({ kind: event.target.value as PayeeKind })}
              className={INPUT_CLASS}
            >
              {PAYEE_KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {PAYEE_KIND_LABELS[kind]}
                </option>
              ))}
            </select>
          </Field>
          <Field id="payee-status" label="Estado">
            <select
              id="payee-status"
              value={draft.status}
              onChange={(event) => update({ status: event.target.value as PayeeStatus })}
              className={INPUT_CLASS}
            >
              {PAYEE_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {PAYEE_STATUS_LABELS[status]}
                </option>
              ))}
            </select>
          </Field>
          <Field id="payee-method" label="Medio de pago">
            <select
              id="payee-method"
              value={draft.payment_method}
              onChange={(event) => update({ payment_method: event.target.value as PaymentMethod })}
              className={INPUT_CLASS}
            >
              {PAYMENT_METHODS.map((method) => (
                <option key={method} value={method}>
                  {PAYMENT_METHOD_LABELS[method]}
                </option>
              ))}
            </select>
          </Field>
          <Field id="payee-category" label="Categoría habitual">
            <select
              id="payee-category"
              value={draft.default_category}
              onChange={(event) => update({ default_category: event.target.value as PaymentCategory | "" })}
              className={INPUT_CLASS}
            >
              <option value="">Sin categoría</option>
              {PAYMENT_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {CATEGORY_LABELS[category]}
                </option>
              ))}
            </select>
          </Field>
          <Field id="payee-currency" label="Moneda de cobro">
            <input
              id="payee-currency"
              required
              maxLength={CURRENCY_CODE_LENGTH}
              value={draft.currency}
              onChange={(event) => update({ currency: event.target.value })}
              className={`${INPUT_CLASS} uppercase`}
            />
          </Field>
          <Field id="payee-per-payment" label="Máximo por pago (USD)" hint="Vacío: usa el tope de la política.">
            <input
              id="payee-per-payment"
              inputMode="decimal"
              value={draft.per_payment_max_usd}
              onChange={(event) => update({ per_payment_max_usd: event.target.value })}
              className={`${INPUT_CLASS} tabular-nums`}
            />
          </Field>
          <Field id="payee-monthly" label="Presupuesto mensual (USD)">
            <input
              id="payee-monthly"
              inputMode="decimal"
              value={draft.monthly_budget_usd}
              onChange={(event) => update({ monthly_budget_usd: event.target.value })}
              className={`${INPUT_CLASS} tabular-nums`}
            />
          </Field>
          <Field id="payee-agreed" label="Monto acordado (USD)" hint="Facturas fuera de lo acordado van a revisión.">
            <input
              id="payee-agreed"
              inputMode="decimal"
              value={draft.agreed_amount_usd}
              onChange={(event) => update({ agreed_amount_usd: event.target.value })}
              className={`${INPUT_CLASS} tabular-nums`}
            />
          </Field>
          <Field id="payee-tolerance" label="Tolerancia (%)">
            <input
              id="payee-tolerance"
              inputMode="decimal"
              value={draft.agreed_tolerance_pct}
              onChange={(event) => update({ agreed_tolerance_pct: event.target.value })}
              className={`${INPUT_CLASS} tabular-nums`}
            />
          </Field>
        </div>
        {isNew && <p className={HINT_CLASS}>Después de crearlo, agrega sus identificadores en la tarjeta.</p>}
        {dialogError && (
          <p role="alert" className="text-sm text-danger">
            {dialogError}
          </p>
        )}
        <div className="flex justify-end gap-2 border-t border-line pt-4">
          <button type="button" onClick={() => dialogRef.current?.close()} className={SECONDARY_BUTTON_CLASS}>
            Cancelar
          </button>
          <button type="submit" disabled={isSaving || !draft.display_name.trim()} className={PRIMARY_BUTTON_CLASS}>
            {isSaving ? "Guardando..." : "Guardar"}
          </button>
        </div>
      </form>
    </dialog>
  );
}

function Field({
  id,
  label,
  hint,
  className = "",
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      <label htmlFor={id} className={LABEL_CLASS}>
        {label}
      </label>
      {children}
      {hint && <p className={HINT_CLASS}>{hint}</p>}
    </div>
  );
}

function PayeesSkeleton() {
  return (
    <ul aria-hidden className="grid gap-3 md:grid-cols-2">
      {[0, 1, 2, 3].map((card) => (
        <li key={card} className={`${CARD_CLASS} space-y-3 p-4`}>
          <div className="h-4 w-1/2 animate-pulse rounded bg-sunken" />
          <div className="h-3 w-1/3 animate-pulse rounded bg-sunken" />
          <div className="h-16 animate-pulse rounded bg-sunken" />
        </li>
      ))}
    </ul>
  );
}
