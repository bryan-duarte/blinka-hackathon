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
const MISSING_POLICY_MESSAGE = "No policy is configured. Run the seed script or create one.";
const SAVE_FAILED_MESSAGE = "The policy could not be saved. Check the values.";
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
  if (hasNegativeOrInvalid) return "Every amount must be a number greater than or equal to 0.";
  if (Number(form.autoPayMax) > Number(form.hardCap)) {
    return "The auto-pay limit cannot exceed the per-payment cap.";
  }
  const probabilities = [form.minFieldConfidence, form.minCategoryConfidence, form.checkerLow, form.checkerHigh];
  const hasOutOfRangeProbability = probabilities.some((probability) => !isProbability(probability));
  if (hasOutOfRangeProbability) {
    return "Confidence thresholds go from 0 to 1.";
  }
  if (Number(form.checkerLow) > Number(form.checkerHigh)) {
    return "The checker low threshold cannot exceed the high one.";
  }
  if (form.currencies.length === 0) return "Add at least one allowed currency.";
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
            <h2 className={SECTION_HEADING_CLASS}>Per-payment and monthly limits</h2>
            <p className={HINT_CLASS}>Current version {policy.version}. All amounts in USD.</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <NumberField
              id="hard-cap"
              label="Per-payment cap"
              hint="Above it, the invoice is held."
              value={form.hardCap}
              onChange={(hardCap) => update({ hardCap })}
            />
            <NumberField
              id="auto-pay-max"
              label="Auto-pay limit"
              hint="Above it, a person must approve."
              value={form.autoPayMax}
              onChange={(autoPayMax) => update({ autoPayMax })}
            />
            <NumberField
              id="monthly-budget"
              label="Monthly budget"
              hint="Total payments in the calendar month."
              value={form.monthlyBudget}
              onChange={(monthlyBudget) => update({ monthlyBudget })}
            />
          </div>
        </section>

        <section className={`${CARD_CLASS} p-5`}>
          <h2 className={SECTION_HEADING_CLASS}>Categories</h2>
          <p className={`${HINT_CLASS} mt-1`}>
            Check the categories the agent can pay. The monthly budget per category is optional.
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
                  <span>Monthly budget</span>
                  <input
                    id={`category-budget-${category}`}
                    inputMode="decimal"
                    placeholder="No cap"
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
          <h2 className={SECTION_HEADING_CLASS}>Allowed currencies</h2>
          <p className={HINT_CLASS}>
            An invoice in another currency, or with no written currency, always goes to review.
          </p>
          <ul className="flex flex-wrap gap-2">
            {form.currencies.map((currency) => (
              <li key={currency}>
                <span className="inline-flex h-8 items-center gap-1 rounded-full bg-sunken pr-1 pl-3 text-sm text-ink tabular-nums">
                  {currency}
                  <button
                    type="button"
                    aria-label={`Remove ${currency}`}
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
              Currency code
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
              Add
            </button>
          </div>
        </section>

        <section className={`${CARD_CLASS} space-y-4 p-5`}>
          <h2 className={SECTION_HEADING_CLASS}>Duplicates and confidence</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField
              id="duplicate-window"
              label="Duplicate window (days)"
              hint="Similar invoices within this window go to review."
              value={form.duplicateWindowDays}
              onChange={(duplicateWindowDays) => update({ duplicateWindowDays })}
            />
            <NumberField
              id="min-field-confidence"
              label="Minimum reading confidence"
              hint="Between 0 and 1. Below it, review."
              value={form.minFieldConfidence}
              onChange={(minFieldConfidence) => update({ minFieldConfidence })}
            />
            <NumberField
              id="min-category-confidence"
              label="Minimum category confidence"
              hint="Between 0 and 1. Protects the category budgets."
              value={form.minCategoryConfidence}
              onChange={(minCategoryConfidence) => update({ minCategoryConfidence })}
            />
            <div className="grid grid-cols-2 gap-3">
              <NumberField
                id="checker-low"
                label="Checker: low"
                value={form.checkerLow}
                onChange={(checkerLow) => update({ checkerLow })}
              />
              <NumberField
                id="checker-high"
                label="Checker: high"
                value={form.checkerHigh}
                onChange={(checkerHigh) => update({ checkerHigh })}
              />
              <p className={`${HINT_CLASS} col-span-2`}>
                Model answers between both values send the invoice to review.
              </p>
            </div>
          </div>
        </section>

        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" disabled={isSaving} className={PRIMARY_BUTTON_CLASS}>
            {isSaving ? "Saving..." : "Save policy"}
          </button>
          <p className={HINT_CLASS} aria-live="polite">
            {savedVersion
              ? `Saved as version ${savedVersion}.`
              : `Saving creates version ${policy.version + 1}; earlier decisions keep theirs.`}
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
        <p className={EYEBROW_CLASS}>This month</p>
        <h2 id="budget-heading" className={`${SECTION_HEADING_CLASS} mt-1`}>
          Budget usage
        </h2>
      </div>
      {hasError && <p className="text-sm text-danger">The budget usage could not be loaded.</p>}
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
          {scope.limit_usd !== null && ` of ${formatMoney(scope.limit_usd, null)}`}
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
  return payees.find((payee) => payee.payee_id === payeeId)?.display_name ?? "Deleted payee";
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
