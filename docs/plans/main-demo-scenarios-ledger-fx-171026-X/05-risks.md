# Risks & Mitigations

## Technical Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Live FX rates move, so FX-sensitive scenarios (MXN, BRL, CLF agreements with a ±3–8% tolerance) flip from paid to review | med | Tolerances sit well above daily FX noise. The 05 validation step runs every scenario after a reset. If the demo must be deterministic, set `BLINKA_FX__LIVE_ENABLED=false` and the static table is used |
| open.er-api.com is down or rate-limited on demo day | med | Order: 2 s timeout, then the stored rate (7 days), then the static table. Rows are marked `cached` or `static_fallback`, so the UI says which rate was used |
| CLF (UF) is missing from open.er-api | low | The static table covers it, and the source is labeled "Fallback rate" |
| Defaulting the guardrail to on breaks local startup and tests that have no guardrail ID | med | Fail-fast error message names the env var. Tests set `enforce=False` explicitly. Document it in `.env.example` |
| The reset purge misses an FK path and fails, leaving partial data | high | One transaction (all or nothing). Nulling steps break the cycles. Verify the order against the models. `DemoResetFailedError` is surfaced in the UI. `scripts/seed_demo.py --reset` is the CLI escape hatch |
| An in-flight agent run writes rows after the purge | high | Cancel and await the sequencer, inbox and payments tasks per owner before deleting. The reset lock blocks new launches |
| An S3 prefix delete bug wipes other users' objects | high | `delete_prefix` refuses any prefix that doesn't end in `/` or is just `/`, and is only called with `f"{owner_id}/"` |
| fpdf2 PDFs extract differently from `minimal_pdf` (layout, number formatting), so extraction fields drift | med | The 05 validation run covers it. Keep totals arithmetically correct and the currency marker explicit |
| Textract can't OCR the scanned image-only PDF well, so it ends as `no_info` | low | Render at 150 dpi with clear text and slight noise. If it still fails, the expectation becomes "review/no_info" and the card describes it as "unreadable scan" |
| The EICAR string trips local antivirus or a CI scanner on the repo | med | The string is split across a concatenation in code, built at runtime, never exported to `samples/demo-kit/` and never offered as a download |
| The checkpoint doesn't hold the system prompt, or the message format changes across deepagents versions | low | Prepend the system prompt from the prompts registry. The serializer skips unknown message types |
| Recharts default styles clash with DESIGN.md (shadows, animations, colors) | low | `chartTheme.ts` reads CSS tokens. Tooltip styles are overridden. Animation follows reduced-motion |
| Translating the whole console to English is a large diff with regression risk | med | Copy-only changes. Do a `rg` sweep for Spanish characters. Update tests that assert Spanish strings |
| `/demo/login` hands out a token to anyone | med | Only active when `BLINKA_DEMO__ENABLED=true` (default false). The demo account holds fictional data only. Every token issued is logged |

## Integration Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Removing `/inbox/simulate` and `SimulatedEmailKind` breaks existing tests and frontend code | med | Remove both together in 05 and 10. Tests are updated mechanically to `inject` |
| Renaming `RULE_NAMES` changes the JSONB `rule_results.name` for decisions made before the change | low | Reset wipes demo data. The frontend keys labels by `rule_id` |
| Trusted forwarders weaken R05b if misused (any forwarder bypasses the sender check) | med | Identity is still checked from the document (R05 bank account, tax ID, blacklist). The list is explicit per owner, and adding to it is visible in the panel |
| Reviewers send from a non-trusted address, so a "paid" scenario comes back as review | low | The README and panel tell them to add their address first. Escalation is the correct, safe behavior |
| WhatsApp self-send needs the reviewer's phone registered on the sandbox, and only one active sandbox phone may exist per number | med | The README explains the registration step. The presenter can switch the registered phone. Otherwise use email |
| The cross-module read in `accountability` and the cross-module write in `demo` break module ownership | low | This is deliberate and limited to a read model and seed/reset. Both are documented in 03-design |
| The inbox `no_invoice` / `no_info` items may or may not have a run with a bill, so the ledger counts them twice or not at all | med | 09 says to verify the linkage before finalizing the `UNION` exclusion condition |

## Edge Cases Identified

- **Re-running a scenario without a reset**: fresh random invoice numbers avoid exact duplicates. Same payee and amount within 10 days correctly trigger R11 (probable duplicate) → review. This is expected, and the panel says "Reset to replay cleanly".
- **First day of the month**: seeded current-month dates clamp to `month_start`, so all budgets still land in the current period.
- **Month rollover between seed and demo**: if the seed ran last month, the current-month pre-fill no longer applies and the limit scenarios pay. Reset before the demo, or note it on the reset button.
- **Sequence step timeout**: GuardDuty plus a slow LLM can exceed 150 s. The launch is marked failed with "step did not finish in time", and the inbox item keeps processing.
- **Reset while a sequence is waiting**: the sequencer task is cancelled first and its launch is marked cancelled.
- **Concurrent startups** (two workers): `ensure_user` handles `EmailTakenError`. Seeding is skipped when the policy exists, but two workers seeding together could duplicate payees. This is acceptable for a single-process demo; document it.
- **Unknown currency (TRY)**: R09 escalates. There is no USD amount, so the R14 and R13 checks pass with the existing "no USD amount" reason.
- **Old exported repo kit**: due dates are in the past. The rules don't reject overdue bills (verify). The README suggests downloading a fresh kit.
- **CSV injection**: subjects and reasons come from untrusted email text, and cells starting with `= + - @` are prefixed with `'`.
