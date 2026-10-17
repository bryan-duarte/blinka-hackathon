# Risks & Mitigations

## Technical Risks

| Risk | Impact | Mitigation |
|---|---|---|
| A double payment from a retry, a double approve, or two runs for the same bill | high | `payments.bill_id` is UNIQUE and `idempotency_key` is UNIQUE. `reserve()` uses `ON CONFLICT DO NOTHING` and returns the existing row. `execute()` is a compare-and-set from `reserved` to `executed`. The LLM has no pay tool. |
| Two bills spend the same remaining budget | high | `reserve()` runs one conditional `UPDATE ... SET reserved_usd = reserved_usd + :x WHERE reserved_usd + :x <= :limit RETURNING`, per scope, in sorted order, in one transaction. Postgres re-checks the WHERE against the latest row version after the lock wait, so the second bill gets 0 rows, the transaction rolls back and the bill is held for lack of budget. |
| Deadlock between concurrent reservations across scopes | med | Lock the scopes in a fixed sorted order (`category:` < `global` < `payee:`). Create counter rows first with `INSERT ... ON CONFLICT DO NOTHING`. |
| Crash after the budget is reserved but before execution | med | On startup, `recover_unfinished_payments()` re-runs `execute()` on rows still `reserved`. That is idempotent because the compare-and-set and `rail_reference` are deterministic. |
| Crash mid-run leaves a bill in `deciding` | med | The startup sweep appends a REVIEW decision (`error_tecnico`) and sets the bill to `review`. |
| LLM extraction is wrong (amount, currency, name) | high | Each field carries its evidence and confidence (R01). Currency is never inferred. The checker can only escalate. Identity checks rely on deterministic identifiers, not names. |
| Discriminated-union structured output is unreliable | med | Extraction is two steps: classify first, then call `extract` with one concrete subtype schema. The existing JSON-mode fallback in `LlmGatewayService.extract` still applies. |
| `ApiModel` with `Decimal` and `date` from the LLM | low | ApiModel is non-strict, so strings coerce. The prompt asks for plain numbers with a `.` decimal point, and normalizes Chilean formats to that. |
| Autogenerate misses partial unique indexes or names them badly | med | Declare `Index(..., unique=True, postgresql_where=...)` with explicit names on the models. Review the generated migration before `upgrade`. |
| Policy edited while bills are being decided | low | Each decision stores `policy_id` and `policy_version`. The limits passed to `reserve()` come from the policy loaded milliseconds earlier. If a limit is lowered during that gap, one bill can be paid under the old limit. That is accepted for the hackathon. If it ever matters, `reserve()` can read the active policy row `FOR SHARE` inside its transaction. |
| Two admins edit the same payee | low | `PATCH` requires `version`. The update is `WHERE id=:id AND version=:v`, and 0 rows means 409 `payee version conflict`. |

## Integration Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Removing `InvoiceClpAnalysis` breaks the inbox UI | med | The frontend types, `EmailDetail` and `EmailList` are updated in the same change. `BADGES` is a `Record`, so `tsc` flags every missing status. |
| `PromptsService` fails at startup when a `PromptId` has no prompt registered | med | Add and remove the `PromptId` members together with the `PROMPTS` tuple. |
| Inbox emails without an attachment still need the body | low | The body text is always stored on `bill_sources.body_text` and sent to extraction. The attachment is optional. |
| The `run_id` FK from `inbox_emails` to `agent_runs` is still used for status | low | Unchanged. The inbox reads the decision through `payments.get_run(run_id).decision`. |
| The orchestrator still expects `payments_run_id` | low | `initiate_payments` keeps returning `run_id`. A duplicate returns the existing bill's run id and `duplicate: true`. |
| The payments checkpointer goes unused | low | Remove it from `PaymentRunDependencies`. `Checkpointers` still creates it, which is harmless. Note it for later cleanup. |

## Edge Cases Identified

- **The same email is delivered twice by the webhook.** The existing `inbox_emails` unique key and `bill_sources` (email ref) both catch it. The second delivery stops before any run.
- **Same PDF, two different emails.** The document-hash conflict links it as a duplicate, with a HOLD decision that names the original.
- **Email and Telegram at the same instant.** Both sources are new, so two runs start. Both reach `claim_bill`. One INSERT wins the partial unique index and the other gets the conflict and becomes a duplicate. Only one bill can reserve, because `payments.bill_id` is unique.
- **The vendor resends a corrected bill with the same number and a new amount.** The fingerprint differs, so it becomes a new canonical bill. R11 sends it to REVIEW because a close amount or the same number was seen recently.
- **AWS-branded email with a personal bank account.** The name matches the AWS payee, the account is unknown or belongs to a person payee, and AWS is `card_on_file`. R05 holds it.
- **A real vendor changes bank account.** R05 holds it. The fix is a human adding the new account identifier to the payee, then the vendor resending. The hold reason says exactly that.
- **Bill in CLP with `$` only.** Currency is None, so R01 sends it to REVIEW with "moneda ambigua".
- **Amount exactly at a limit.** Comparisons are `>`, so a bill exactly at the limit is allowed.
- **Approve a bill whose budget was spent meanwhile.** The re-decision passes, then reservation fails, so the bill is held with "presupuesto agotado al aprobar".
- **Approve and reject clicked at the same time.** The compare-and-set from `review` to `approving`/`rejected` lets only one through. The other gets 409.
- **Reject, then the same bill is resent.** The fingerprint matches the canonical bill (rejected), so the resend is held as a duplicate. A human must handle it on purpose.
- **A person's cuenta de cobro without an invoice number.** The fingerprint uses the due date. R11 covers the case where the due date also differs.
- **A blacklisted identifier appears on an otherwise valid bill from an allowed payee.** R03 holds it. Blacklist wins over the allowlist.
- **A category appears in the extraction but not in the policy's per-category budgets.** That category has no category cap. The global and payee caps still apply.
- **The checker LLM is down.** Every CHK result becomes REVIEW ("verificador no disponible"). It never fails open.
