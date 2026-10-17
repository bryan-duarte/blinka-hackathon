# User Preferences & Decisions

## 👤 Configuration Preferences

- **Context Level**: Moderado
- **Participation Level**: Equilibrado
- **Detail Level**: Neutral (snippets are orientative; implementer decides final code)

## 💬 Q&A and Rationale

### 🏷️ Decision authority
**Q:** Who has the final say on pay / hold / review, and who triggers the dummy "pay"?
**A:** Hybrid: rules + LLM checker.
**Decision:** A pure `decide()` function evaluates every rule and the strictest effect wins. A second LLM pass (the checker) answers typed questions with a probability, and its output can only add REVIEW reasons. The dummy pay is called by code (`PaymentLedger.execute`) after a PAY verdict, exactly once per bill. The LLM never gets a pay tool. Delete `execute_payment` from `modules/payments/agent.py`.
**Rejected:** Agent-with-guarded-tool keeps the LLM in the money path. Pure rules only loses the fuzzy "does this match the payee's service" signal.

### 🏷️ Config store
**Q:** Where do the rules and the payee registry live?
**A:** DB tables per owner, plus a seed script.
**Decision:** New `payment_policy` module. Tables `payment_policies` (versioned, one active per owner), `payees`, `payee_identifiers` and `blacklist_entries`, all in the product DB. CRUD API. Seed script `backend/scripts/seed_payment_policy.py` loads a demo company for a given user email. Each decision stores `policy_id` and `policy_version`.
**Rejected:** A JSON file has no runtime edits and no per-owner rules. Read-only tables conflict with the config screens that are in scope.

### 🏷️ Ledger DB
**Q:** Which Postgres DB holds the ledger, budget counters and dedup keys?
**A:** Product DB.
**Decision:** Every new table goes on `ProductBase`. Budget reservation and the payment insert happen in one transaction, with foreign keys to `agent_runs`, `files` and `inbox_emails`.
**Rejected:** The payments DB can't share transactions or foreign keys with runs and bills.

### 🏷️ Currency
**Q:** Base currency, and what happens when a bill has no currency?
**A:** USD base, never infer.
**Decision:** All limits are USD. A missing or ambiguous currency (a bare `$`) sets `currency=None`, and rule R01 sends the bill to REVIEW. The extraction prompt forbids guessing. FX uses a dummy USD rate table (`TEMPORAL`). A currency without a rate also goes to REVIEW (R09).
**Rejected:** Inferring from the payee (both CLP and USD variants) would let a guess move money.

### 🏷️ Over-limit semantics
**Q:** Bill over the hard cap, or no budget left?
**A:** Hard cap or budget exhausted → HOLD. Above the auto-pay max → REVIEW.
**Decision:** R12 `hard_cap` gives HOLD. R13 `auto_pay_max` gives REVIEW. R14 `budget_available` gives HOLD, and so does the reservation-time check. Approving a REVIEW bill waives only rules whose effect is REVIEW. HOLD rules stay binding, and budget is re-checked at approval time.
**Rejected:** "Everything over a limit goes to review" makes the limits advisory.

### 🏷️ Category cap
**Q:** What does "max per category" limit?
**A:** The monthly budget per category.
**Decision:** `payment_policies.category_monthly_budgets_usd` is a JSONB map from category to USD. Counter scope is `category:<name>`, using the same atomic counter as the global budget.
**Rejected:** A per-bill max per category is not a budget for a period.

### 🏷️ Category source
**Q:** Where does a bill's category come from?
**A:** The LLM infers it for each bill.
**Decision:** The extraction returns `category` plus `category_confidence`. Rule R08 sends the bill to REVIEW when the confidence is below `min_category_confidence`, or when the matched payee has a `default_category` that differs. This guards the per-category budget against misclassification.
**Rejected:** Category from the registry only (the user chose LLM inference).

### 🏷️ Duplicates
**Q:** What happens when the same bill arrives again?
**A:** An exact duplicate is held and linked to the original. A fuzzy duplicate goes to REVIEW.
**Decision:** There are three exact layers:
1. `bill_sources` UNIQUE on (owner, source_type, source_ref). A repeat of the same delivery stops at intake, before any run starts.
2. `bills` partial UNIQUE on (owner, document_sha256).
3. `bills` partial UNIQUE on (owner, fingerprint).

When layer 2 or 3 conflicts, the bill is stored with `duplicate_of_bill_id` and gets a HOLD decision that names the original. The fuzzy rule R11 (same payee, amount within ±0.5% inside `duplicate_window_days`, invoice number missing or different) gives REVIEW.
**Rejected:** Silent drops lose traceability. Sending every duplicate to review adds human load for no gain.

### 🏷️ Payee matching and impersonation
**Q:** How is a bill matched to a payee?
**A:** Identifiers first, then aliases. The user added: *"if somebody sends an email with their personal account number pretending to be an AWS bill or a provider company, this needs to be identified."*
**Decision:** Matching order is tax_id → bank_account → service_account_id → sender email → sender domain → normalized name or alias. Partial name matches are never trusted.

Rule R05 `identity_consistent` holds the bill when any of these is true:
- strong identifiers resolve to more than one payee;
- the name or alias resolves to payee A but a strong identifier on the bill is unknown or belongs to someone else;
- the bill's bank account isn't registered for the matched payee;
- the matched payee's `payment_method` isn't `bank_transfer` (for example AWS uses `card_on_file`) but the bill asks for a transfer to an account;
- the bill is classified `service` or `company` but its bank account belongs to a registered `person` payee.

A sender email or domain that doesn't match the payee's registered ones gives REVIEW on its own, and HOLD when combined with an account mismatch. A UNIQUE constraint on (owner, kind, normalized_value) in `payee_identifiers` guarantees that each identifier belongs to exactly one payee.
**Rejected:** LLM fuzzy matching lets a lookalike name ("Amaz0n") through.

### 🏷️ Review scope
**Q:** Which human-review pieces are in scope?
**A:** Backend, the inbox UI and config screens.
**Decision:**
- Endpoints: `POST /bills/{id}/approve` and `POST /bills/{id}/reject`.
- Inbox: a decision card with verdict, explanation, each rule's result and evidence, a duplicate link, and Approve/Reject buttons (shown only for review).
- New pages: `/settings/policy`, `/settings/payees` and `/settings/blacklist`.

**Rejected:** Backend-only, and backend plus inbox without the config screens.

### 🏷️ Budget period
**Q:** What is the budget period?
**A:** Calendar month, UTC.
**Decision:** `budget_counters` has one row per (owner, scope, period) with period like `"2026-10"`. A new month starts implicitly with a new row.
**Rejected:** A period configurable per rule adds code for the hackathon.

### 🏷️ Sources
**Q:** How far does multi-source support go now?
**A:** Email and chat now, Telegram-ready.
**Decision:** `BillSourceType` covers `email | chat | upload | telegram`. Email (inbox pipeline), chat (`initiate_payments`) and upload (`POST /payments/runs`) all register sources. Telegram gets only the enum value and the `BillSourceIntake` contract. No adapter yet.
**Rejected:** Email only would leave chat as an unguarded second path.

### 🏷️ Agent-decided (no question asked)
- **Extraction is a two-step LLM call** (classify, then a schema per kind) through `LlmGatewayClient.extract`. A discriminated union in one structured-output call is less reliable on tool-schema providers.
- **The checker is a single `llm.extract` call** with `model_kind="payments"`, not a deep agent. The deep agent, `convert_to_clp` and the per-run payments checkpointer go away from the payments run.
- **Explanations are deterministic Spanish templates** built from rule results, with real figures. The checker's rationale is shown separately, labeled as the model's opinion. No free LLM narration.
- **A prompt-injection text addressed to the agent gives HOLD** (R02). The Bedrock guardrail still screens upstream.
- **Agreement match is added (R17)** for the `CLAUDE.md` trap "factura que no cuadra con lo acordado". Payees get optional `agreed_amount_usd` and `agreed_tolerance_pct`.
- **Fail-closed.** Any exception after a bill exists records a REVIEW decision with reason `error_tecnico` instead of only marking the run FAILED.
- **Money is `Decimal` end to end.** USD columns are `Numeric(18, 2)` and original amounts are `Numeric(18, 4)`.
- **The plan folder name** follows the skill's convention (`main-payment-rules-dedup-review-171026`). The existing plans carry a `-X` suffix, which likely marks applied plans.
