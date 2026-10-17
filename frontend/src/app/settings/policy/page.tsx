"use client";

import { type FormEvent, useEffect, useState } from "react";
import { useReportError } from "@/components/settings/errors";
import {
  CARD_CLASS,
  EYEBROW_CLASS,
  HINT_CLASS,
  INPUT_CLASS,
  LABEL_CLASS,
  PRIMARY_BUTTON_CLASS,
  SECTION_HEADING_CLASS,
} from "@/components/settings/styles";
import { api } from "@/lib/api";
import { CURRENCY_CODE_LENGTH, formatMoney } from "@/lib/format";
import { CATEGORY_LABELS, PAYMENT_CATEGORIES } from "@/lib/labels";
import type {
  BudgetUsageView,
  PayeeView,
  PaymentCategory,
  PaymentPolicyUpdate,
  PaymentPolicyView,
} from "@/lib/types";

const CURRENCY_CODE_PATTERN = /^[A-Z]{3}$/;
const PERCENT = 100;
const FULL_USAGE_PERCENT = 100;
const NEAR_LIMIT_PERCENT = 90;
const MAX_PROBABILITY = 1;
const MISSING_POLICY_MESSAGE = "No hay una política configurada. Ejecuta el script de semilla o crea una.";
const SAVE_FAILED_MESSAGE = "No se pudo guardar la política. Revisa los valores.";
const GLOBAL_SCOPE = "global";
const CATEGORY_SCOPE_PREFIX = "category:";
const PAYEE_SCOPE_PREFIX = "payee:";

type PolicyForm = {
  hardCap: string;
  autoPayMax: string;
  monthlyBudget: string;
  categoryBudgets: Record<PaymentCategory, string>;
  allowedCategories: Set<PaymentCategory>;
  currencies: string[];
  duplicateWindowDays: string;
  minFieldConfidence: string;
  minCategoryConfidence: string;
  checkerLow: string;
  checkerHigh: string;
};

function toForm(policy: PaymentPolicyView): PolicyForm {
  const categoryBudgets = Object.fromEntries(
    PAYMENT_CATEGORIES.map((category) => [category, policy.category_monthly_budgets_usd[category] ?? ""]),
  ) as Record<PaymentCategory, string>;
  return {
    hardCap: policy.hard_cap_per_payment_usd,
    autoPayMax: policy.auto_pay_max_usd,
    monthlyBudget: policy.monthly_budget_usd,
    categoryBudgets,
    allowedCategories: new Set(policy.allowed_categories),
    currencies: policy.allowed_currencies,
    duplicateWindowDays: String(policy.duplicate_window_days),
    minFieldConfidence: policy.min_field_confidence,
    minCategoryConfidence: policy.min_category_confidence,
    checkerLow: policy.checker_review_low,
    checkerHigh: policy.checker_review_high,
  };
}

function toUpdate(form: PolicyForm): PaymentPolicyUpdate {
  const categoryBudgets = Object.fromEntries(
    Object.entries(form.categoryBudgets).filter(([, budget]) => budget.trim() !== ""),
  );
  return {
    hard_cap_per_payment_usd: form.hardCap,
    auto_pay_max_usd: form.autoPayMax,
    monthly_budget_usd: form.monthlyBudget,
    category_monthly_budgets_usd: categoryBudgets,
    allowed_categories: PAYMENT_CATEGORIES.filter((category) => form.allowedCategories.has(category)),
    allowed_currencies: form.currencies,
    duplicate_window_days: Number(form.duplicateWindowDays),
    min_field_confidence: form.minFieldConfidence,
    min_category_confidence: form.minCategoryConfidence,
    checker_review_low: form.checkerLow,
    checker_review_high: form.checkerHigh,
  };
}

function validationError(form: PolicyForm): string | null {
  const amounts = [form.hardCap, form.autoPayMax, form.monthlyBudget, ...Object.values(form.categoryBudgets)];
  const hasNegativeOrInvalid = amounts.some((amount) => amount.trim() !== "" && !(Number(amount) >= 0));
  if (hasNegativeOrInvalid) return "Todos los montos deben ser números mayores o iguales a 0.";
  if (Number(form.autoPayMax) > Number(form.hardCap)) {
    return "El tope de autopago no puede superar el tope por pago.";
  }
  const probabilities = [form.minFieldConfidence, form.minCategoryConfidence, form.checkerLow, form.checkerHigh];
  const hasOutOfRangeProbability = probabilities.some((probability) => !isProbability(probability));
  if (hasOutOfRangeProbability) {
    return "Los umbrales de confianza van entre 0 y 1.";
  }
  if (Number(form.checkerLow) > Number(form.checkerHigh)) {
    return "El umbral bajo del verificador no puede superar al alto.";
  }
  if (form.currencies.length === 0) return "Agrega al menos una moneda permitida.";
  return null;
}

function isProbability(value: string): boolean {
  const probability = Number(value);
  return probability >= 0 && probability <= MAX_PROBABILITY;
}

export default function PolicyPage() {
  const reportError = useReportError();
  const [policy, setPolicy] = useState<PaymentPolicyView | null>(null);
  const [form, setForm] = useState<PolicyForm | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedVersion, setSavedVersion] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [currencyDraft, setCurrencyDraft] = useState("");

  useEffect(() => {
    api
      .policy()
      .then((loadedPolicy) => {
        setPolicy(loadedPolicy);
        setForm(toForm(loadedPolicy));
      })
      .catch((error: unknown) =>
        setLoadError(reportError(error, MISSING_POLICY_MESSAGE, MISSING_POLICY_MESSAGE)),
      );
  }, [reportError]);

  function update(changes: Partial<PolicyForm>) {
    setForm((current) => (current ? { ...current, ...changes } : current));
    setSavedVersion(null);
  }

  function addCurrency() {
    if (!form) return;
    const currencyCode = currencyDraft.trim().toUpperCase();
    if (!CURRENCY_CODE_PATTERN.test(currencyCode) || form.currencies.includes(currencyCode)) return;
    update({ currencies: [...form.currencies, currencyCode] });
    setCurrencyDraft("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form) return;
    const invalidReason = validationError(form);
    if (invalidReason) {
      setSaveError(invalidReason);
      return;
    }
    setIsSaving(true);
    setSaveError(null);
    try {
      const savedPolicy = await api.updatePolicy(toUpdate(form));
      setPolicy(savedPolicy);
      setForm(toForm(savedPolicy));
      setSavedVersion(savedPolicy.version);
    } catch (error) {
      setSaveError(reportError(error, SAVE_FAILED_MESSAGE, SAVE_FAILED_MESSAGE));
    } finally {
      setIsSaving(false);
    }
  }

  if (loadError) {
    return (
      <p role="alert" className={`${CARD_CLASS} p-5 text-sm text-danger`}>
        {loadError}
      </p>
    );
  }
  if (!policy || !form) return <PolicySkeleton />;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <form onSubmit={save} className="space-y-6" noValidate>
        <section className={`${CARD_CLASS} space-y-4 p-5`}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className={SECTION_HEADING_CLASS}>Límites por pago y por mes</h2>
            <p className={HINT_CLASS}>Versión actual {policy.version}. Todos los montos en USD.</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <NumberField
              id="hard-cap"
              label="Tope por pago"
              hint="Por encima, la factura se frena."
              value={form.hardCap}
              onChange={(hardCap) => update({ hardCap })}
            />
            <NumberField
              id="auto-pay-max"
              label="Tope de autopago"
              hint="Por encima, pide aprobación humana."
              value={form.autoPayMax}
              onChange={(autoPayMax) => update({ autoPayMax })}
            />
            <NumberField
              id="monthly-budget"
              label="Presupuesto mensual"
              hint="Total de pagos del mes calendario."
              value={form.monthlyBudget}
              onChange={(monthlyBudget) => update({ monthlyBudget })}
            />
          </div>
        </section>

        <section className={`${CARD_CLASS} p-5`}>
          <h2 className={SECTION_HEADING_CLASS}>Categorías</h2>
          <p className={`${HINT_CLASS} mt-1`}>
            Marca las categorías que el agente puede pagar. El presupuesto mensual por categoría es opcional.
          </p>
          <ul className="mt-4 divide-y divide-line">
            {PAYMENT_CATEGORIES.map((category) => (
              <li key={category} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                <label className="flex min-h-10 items-center gap-2.5 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={form.allowedCategories.has(category)}
                    onChange={(event) => {
                      const allowedCategories = new Set(form.allowedCategories);
                      if (event.target.checked) allowedCategories.add(category);
                      else allowedCategories.delete(category);
                      update({ allowedCategories });
                    }}
                    className="size-4 accent-accent"
                  />
                  {CATEGORY_LABELS[category]}
                </label>
                <label className="flex items-center gap-2 text-xs text-muted">
                  <span>Presupuesto mensual</span>
                  <input
                    id={`category-budget-${category}`}
                    inputMode="decimal"
                    placeholder="Sin tope"
                    value={form.categoryBudgets[category]}
                    onChange={(event) =>
                      update({
                        categoryBudgets: { ...form.categoryBudgets, [category]: event.target.value },
                      })
                    }
                    className={`${INPUT_CLASS} w-32 text-right tabular-nums`}
                  />
                </label>
              </li>
            ))}
          </ul>
        </section>

        <section className={`${CARD_CLASS} space-y-3 p-5`}>
          <h2 className={SECTION_HEADING_CLASS}>Monedas permitidas</h2>
          <p className={HINT_CLASS}>
            Una factura en otra moneda, o sin moneda escrita, siempre pasa a revisión.
          </p>
          <ul className="flex flex-wrap gap-2">
            {form.currencies.map((currency) => (
              <li key={currency}>
                <span className="inline-flex h-8 items-center gap-1 rounded-full bg-sunken pr-1 pl-3 text-sm text-ink tabular-nums">
                  {currency}
                  <button
                    type="button"
                    aria-label={`Quitar ${currency}`}
                    onClick={() => update({ currencies: form.currencies.filter((code) => code !== currency) })}
                    className="grid size-6 place-items-center rounded-full text-muted hover:bg-line hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
                  >
                    ×
                  </button>
                </span>
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <label htmlFor="currency-draft" className="sr-only">
              Código de moneda
            </label>
            <input
              id="currency-draft"
              value={currencyDraft}
              maxLength={CURRENCY_CODE_LENGTH}
              placeholder="EUR"
              onChange={(event) => setCurrencyDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  addCurrency();
                }
              }}
              className={`${INPUT_CLASS} w-24 uppercase`}
            />
            <button
              type="button"
              onClick={addCurrency}
              className="h-10 rounded-md border border-line px-3 text-sm text-ink hover:bg-sunken focus-visible:outline-2 focus-visible:outline-accent"
            >
              Agregar
            </button>
          </div>
        </section>

        <section className={`${CARD_CLASS} space-y-4 p-5`}>
          <h2 className={SECTION_HEADING_CLASS}>Duplicados y confianza</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField
              id="duplicate-window"
              label="Ventana de duplicados (días)"
              hint="Facturas parecidas dentro de este plazo pasan a revisión."
              value={form.duplicateWindowDays}
              onChange={(duplicateWindowDays) => update({ duplicateWindowDays })}
            />
            <NumberField
              id="min-field-confidence"
              label="Confianza mínima de lectura"
              hint="Entre 0 y 1. Por debajo, revisión."
              value={form.minFieldConfidence}
              onChange={(minFieldConfidence) => update({ minFieldConfidence })}
            />
            <NumberField
              id="min-category-confidence"
              label="Confianza mínima de categoría"
              hint="Entre 0 y 1. Protege los presupuestos por categoría."
              value={form.minCategoryConfidence}
              onChange={(minCategoryConfidence) => update({ minCategoryConfidence })}
            />
            <div className="grid grid-cols-2 gap-3">
              <NumberField
                id="checker-low"
                label="Verificador: bajo"
                value={form.checkerLow}
                onChange={(checkerLow) => update({ checkerLow })}
              />
              <NumberField
                id="checker-high"
                label="Verificador: alto"
                value={form.checkerHigh}
                onChange={(checkerHigh) => update({ checkerHigh })}
              />
              <p className={`${HINT_CLASS} col-span-2`}>
                Respuestas del modelo entre ambos valores envían la factura a revisión.
              </p>
            </div>
          </div>
        </section>

        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" disabled={isSaving} className={PRIMARY_BUTTON_CLASS}>
            {isSaving ? "Guardando..." : "Guardar política"}
          </button>
          <p className={HINT_CLASS} aria-live="polite">
            {savedVersion
              ? `Guardada como versión ${savedVersion}.`
              : `Guardar crea la versión ${policy.version + 1}; las decisiones anteriores conservan la suya.`}
          </p>
        </div>
        {saveError && (
          <p role="alert" className="text-sm text-danger">
            {saveError}
          </p>
        )}
      </form>
      <BudgetPanel policyVersion={policy.version} />
    </div>
  );
}

function NumberField({
  id,
  label,
  hint,
  value,
  onChange,
}: {
  id: string;
  label: string;
  hint?: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className={LABEL_CLASS}>
        {label}
      </label>
      <input
        id={id}
        inputMode="decimal"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`${INPUT_CLASS} tabular-nums`}
      />
      {hint && <p className={HINT_CLASS}>{hint}</p>}
    </div>
  );
}

function BudgetPanel({ policyVersion }: { policyVersion: number }) {
  const [usage, setUsage] = useState<BudgetUsageView[] | null>(null);
  const [payees, setPayees] = useState<PayeeView[]>([]);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    Promise.all([api.budgets(), api.payees()])
      .then(([budgetUsage, loadedPayees]) => {
        setUsage(budgetUsage);
        setPayees(loadedPayees);
      })
      .catch(() => setHasError(true));
  }, [policyVersion]);

  return (
    <aside className={`${CARD_CLASS} h-fit space-y-4 p-5`} aria-labelledby="budget-heading">
      <div>
        <p className={EYEBROW_CLASS}>Este mes</p>
        <h2 id="budget-heading" className={`${SECTION_HEADING_CLASS} mt-1`}>
          Uso del presupuesto
        </h2>
      </div>
      {hasError && <p className="text-sm text-danger">No se pudo cargar el uso del presupuesto.</p>}
      {!hasError && usage === null && (
        <div aria-hidden className="space-y-3">
          {[0, 1, 2].map((row) => (
            <div key={row} className="h-8 animate-pulse rounded bg-sunken" />
          ))}
        </div>
      )}
      {usage && (
        <ul className="space-y-4">
          {usage.map((scope) => (
            <BudgetBar key={scope.scope} scope={scope} label={scopeLabel(scope.scope, payees)} />
          ))}
        </ul>
      )}
    </aside>
  );
}

function BudgetBar({ scope, label }: { scope: BudgetUsageView; label: string }) {
  const limit = scope.limit_usd !== null ? Number(scope.limit_usd) : null;
  const reserved = Number(scope.reserved_usd);
  const usedPercent = limit ? Math.min(FULL_USAGE_PERCENT, (reserved / limit) * PERCENT) : 0;
  const isNearLimit = usedPercent >= NEAR_LIMIT_PERCENT;
  return (
    <li className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="truncate text-ink">{label}</span>
        <span className="shrink-0 text-xs text-muted tabular-nums">
          {formatMoney(scope.reserved_usd, null)}
          {scope.limit_usd !== null && ` de ${formatMoney(scope.limit_usd, null)}`}
        </span>
      </div>
      {limit !== null && (
        <div
          role="progressbar"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={limit}
          aria-valuenow={reserved}
          className="h-1.5 overflow-hidden rounded-full bg-sunken"
        >
          <div
            className={`h-full rounded-full ${isNearLimit ? "bg-danger" : "bg-accent"}`}
            style={{ width: `${usedPercent}%` }}
          />
        </div>
      )}
    </li>
  );
}

function scopeLabel(scope: string, payees: PayeeView[]): string {
  if (scope === GLOBAL_SCOPE) return "Global";
  if (scope.startsWith(CATEGORY_SCOPE_PREFIX)) {
    const category = scope.slice(CATEGORY_SCOPE_PREFIX.length) as PaymentCategory;
    return CATEGORY_LABELS[category] ?? category;
  }
  const payeeId = scope.slice(PAYEE_SCOPE_PREFIX.length);
  return payees.find((payee) => payee.payee_id === payeeId)?.display_name ?? "Beneficiario eliminado";
}

function PolicySkeleton() {
  return (
    <div aria-hidden className="space-y-6">
      {[0, 1, 2].map((block) => (
        <div key={block} className={`${CARD_CLASS} space-y-3 p-5`}>
          <div className="h-4 w-1/3 animate-pulse rounded bg-sunken" />
          <div className="h-10 animate-pulse rounded bg-sunken" />
        </div>
      ))}
    </div>
  );
}
