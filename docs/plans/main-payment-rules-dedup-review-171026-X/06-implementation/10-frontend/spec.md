# Frontend Implementation

## Overview

This step shows the agent's decision in the inbox: verdict, explanation, each rule's result, evidence, the duplicate link and the checker's opinion. It lets a human approve or reject bills in review. It also adds settings screens for the payment policy, the payee registry and the blacklist. All of it reuses the existing design system in `frontend/src/app/globals.css` (stone surfaces, ink-blue accent, semantic `success`/`warning`/`danger` tokens, mono numerals) and the Spanish UI copy.

Load the `frontend-design` skill before writing components.

## Files to Modify/Create

- `frontend/src/lib/types.ts`
  - `InboxEmailStatus`: remove `"analyzed"`, add `"paid" | "held" | "review" | "duplicate"`.
  - Add the types `Verdict`, `RuleEffect`, `RuleResult`, `CheckerAnswer`, `CheckerAssessment`, `PaymentCandidate` (a union on `kind`), `BillDecisionView`, `BillDetail`, `PaymentView`, `BudgetUsageView`, `PaymentPolicyView`, `PaymentPolicyUpdate`, `PayeeView`, `PayeeCreate`, `PayeeUpdate`, `PayeeIdentifierCreate`, `BlacklistEntryView`, `BlacklistEntryCreate`, `PaymentCategory`, `PayeeKind`, `PaymentMethod` and `IdentifierKind`.
  - Replace `InvoiceClpAnalysis` with `decision: BillDecisionView | null` on `InboxEmailView`.
  - Extend `SimulatedEmailKind` with the new kinds from 08.
  - Decimals arrive as JSON strings (Pydantic serializes `Decimal` as `str`), so type them as `string` and format them with `formatAmount(Number(x), currency)`.
- `frontend/src/lib/api.ts`: add `policy()`, `updatePolicy(body)`, `payees()`, `createPayee(body)`, `updatePayee(id, body)`, `deletePayee(id)`, `addIdentifier(id, body)`, `deleteIdentifier(id, identifierId)`, `blacklist()`, `addBlacklist(body)`, `deleteBlacklist(id)`, `bills(status?)`, `bill(id)`, `approveBill(id, note)`, `rejectBill(id, note)` and `budgets(period?)`. Use the existing `request<T>` helper.
- `frontend/src/components/inbox/StatusBadge.tsx`: add `BADGES` entries:
  - `paid`: "Pagado", success
  - `held`: "Frenado", danger
  - `review`: "En revisión", warning
  - `duplicate`: "Duplicado", muted/sunken

  Remove `analyzed`.
- `frontend/src/components/inbox/EmailDetail.tsx`: `ResultCard` routes `paid | held | review | duplicate` to `<DecisionCard decision={email.decision} />`. Delete `AnalysisCard`. Change the analyzing copy to "El agente está evaluando la factura contra las reglas...".
- `frontend/src/components/inbox/EmailList.tsx`: the amount column shows `decision.amount` with its currency, plus a `≈ USD` line when the currency isn't USD.
- `frontend/src/components/bills/DecisionCard.tsx` (new):
  1. A verdict header: a large chip, `explanation`, payee, amount, `≈ USD` and category.
  2. The rule list. Failing rules come first: HOLD with a danger stripe, then REVIEW with a warning stripe. Passing rules are collapsed under a "N reglas cumplidas" disclosure. Each row shows `rule_id`, `name` and `reason`.
  3. "Datos leídos de la factura": a table of candidate fields, each with its evidence quote in mono and its confidence.
  4. "Opinión del verificador (modelo)": the CHK answers with probability and rationale, visually secondary.
  5. For a duplicate, a link that selects the original bill's email, or opens `/bills/{id}`.
  6. The decision history, when there is more than one entry: actor (Agente or Persona), verdict, note and time.
- `frontend/src/components/bills/ReviewActions.tsx` (new): rendered only when `decision.can_approve`.
  - A required note textarea (3–500 characters), plus "Aprobar pago" and "Rechazar" buttons.
  - Disable the buttons while a request is in flight. On a 409, show "Esta factura ya fue resuelta por otra persona." and refetch.
  - After success, refetch the email. The decision may come back as `held` (for example, budget ran out at approval), and the card must make that clear.
- `frontend/src/app/settings/layout.tsx` (new): a shared settings shell with tabs Política, Beneficiarios and Lista negra, a back link to `/inbox`, and the auth guard that `app/inbox/page.tsx` uses (`tokenStore` plus a redirect on `UnauthorizedError`).
- `frontend/src/app/settings/policy/page.tsx` (new): a form for the hard cap, auto-pay max, monthly budget, per-category budgets (a row per category), allowed categories (checkboxes), allowed currencies (chips), duplicate window, confidence thresholds and the checker band.
  - Client-side validation: auto-pay max must be ≤ the hard cap, and every value must be ≥ 0.
  - Show the current `version` and "Guardar crea la versión N+1".
  - Below the form, a budget usage panel from `api.budgets()` with one bar per scope (used / limit).
- `frontend/src/app/settings/payees/page.tsx` (new): a list grouped by kind (Servicios, Personas, Empresas) showing status, payment method, category and limits.
  - Create/edit dialog fields: kind, name, status, payment method, default category, currency, per-payment max, monthly budget, agreed amount and tolerance.
  - Identifier manager: kind select plus value. A 409 shows "Este identificador ya pertenece a otro beneficiario".
  - The edit sends `version`. A 409 shows "Alguien modificó este beneficiario; recarga para ver los cambios".
- `frontend/src/app/settings/blacklist/page.tsx` (new): a table of entries (kind, value, reason) with add and delete.
- `frontend/src/app/inbox/page.tsx`
  - Add the new `SIMULATION_OPTIONS` with Spanish labels such as "Suplantación de AWS (cuenta personal)" and "Supera tope de autopago".
  - Add a "Configuración" link to `/settings/policy` in the header.
  - Add a status filter chip "En revisión", applied client-side on `emails`.
- `frontend/src/app/layout.tsx`: change `lang` to `"es"`.

## Implementation Guidelines

- Keep polling as it is. `review` is not in `PENDING_STATUSES`; it's a resting state that waits for a person, so the badge doesn't pulse.
- Show money with `formatAmount` (es-CL), in tabular mono. Show masked accounts exactly as the backend sends them; never reconstruct them.
- Rule rows must encode state in shape and in color: a left stripe plus an icon glyph (✕ hold, ! review, ✓ pass). Semantic colors must not reuse the accent.
- Write copy from the finance user's side: "Frenado: la cuenta no es la registrada para Amazon Web Services", not "R05 failed".
- Every form control gets a stable `id` and a `<label>`, and keyboard focus must be visible (`focus-visible:outline-accent`, as existing components do).
- At phone width, the settings tables become stacked cards.

Orientative `DecisionCard` skeleton:

```tsx
export function DecisionCard({ decision }: { decision: BillDecisionView }) {
  const failing = decision.rule_results.filter((rule) => rule.effect !== "pass");
  const passing = decision.rule_results.filter((rule) => rule.effect === "pass");
  return (
    <section className="flex flex-col gap-4 rounded-md border border-line bg-panel p-4">
      <VerdictHeader decision={decision} />
      <RuleList rules={sortByEffect(failing)} />
      <details><summary>{passing.length} reglas cumplidas</summary><RuleList rules={passing} /></details>
      {decision.candidate && <EvidenceTable candidate={decision.candidate} />}
      {decision.checker && <CheckerOpinion checker={decision.checker} />}
      {decision.can_approve && <ReviewActions billId={decision.bill_id} />}
    </section>
  );
}
```

## Dependencies

- No new npm packages.
- Backend routes from 09.
- The `frontend-design` skill.

## Integration Notes

- `BADGES` is `Record<InboxEmailStatus, ...>`, so `tsc` (`pnpm build`) fails until every new status has a badge. Use that as the completeness check.
- `GET /bills/{id}` provides the history for `DecisionCard`. The inbox detail only carries the latest decision, so fetch `api.bill(decision.bill_id)` lazily when the history section is expanded.
