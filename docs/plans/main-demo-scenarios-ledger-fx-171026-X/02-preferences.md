# User Preferences & Decisions

## 👤 Configuration Preferences

- **Context Level**: Moderado
- **Participation Level**: Control pleno
- **Detail Level**: Neutral

## 💬 Q&A and Rationale

### 🏷️ Demo account & seed data

**Q:** How should the demo user exist?
**A:** Fixed demo account.
**Decision:** There is one `demo@blinka.dev` account, configured via `DemoSettings`. Only that account may launch scenarios or reset. Demo routes are gated by comparing the current user's email with `settings.demo.email`, so no `is_demo` column is needed.
**Rejected:** A "seed any account" option would expose a destructive reset to every user.

**Q:** Which fictional company?
**A:** A US company with a LatAm team.
**Decision:** The company is "Andescape Labs, Inc." (Delaware, USD base). The existing AWS, ACME Cloud, Sisur and María José payees are kept, and payees are added for CO (COP), MX (MXN), BR (BRL) and DE (EUR), plus a CLF-denominated rent.
**Rejected:** Keeping only the current seed is too thin. Aligning to `samples/invoices` would rewrite everything.

**Q:** Contact types?
**A:** Persons, companies, services and blacklist entries, all four.
**Decision:** The seed includes all four kinds (see 04-demo-seed).

**Q:** History depth?
**A:** 3 past months plus the current month.
**Decision:** That gives about 35–45 historical bills with backdated `created_at`. The current month is pre-filled so that the payee limit and the cloud category cap are nearly reached.

**Q:** How is the demo account created?
**A:** On startup, by a script, and through a login shortcut.
**Decision:** When `BLINKA_DEMO__ENABLED=true`, the lifespan ensures the user exists and seeds it if the policy is missing. `scripts/seed_demo.py` (`--reset`) is the CLI path. `POST /demo/login` returns a token and the login page shows an "Enter the demo" button.

### 🏷️ Scenarios

**Q:** Where does the launcher live?
**A:** Inside the inbox.
**Decision:** It lives in the inbox only; there is no `/demo` page.

**Q:** Inbox layout?
**A:** A slide-over panel.
**Decision:** A "Demo scenarios" button in `ConsoleTopBar` actions opens a right slide-over. The panel has collapsible sections, and each scenario row shows a title, the expected outcome, a fixed channel badge, a "Send" button and step progress. "Reset demo" sits at the bottom behind a confirm dialog. The panel only renders for the demo account. The old simulate dropdown, `/inbox/simulate`, `SimulatedEmailKind` and `samples.py` are removed.

**Q:** Multi-step cases?
**A:** Scripted sequence.
**Decision:** A scenario is an ordered list of steps, and one click runs them all.

**Q:** Sequencing?
**A:** Wait until the previous run finishes.
**Decision:** The `DemoSequencer` background task polls the inbox item until it reaches a terminal status, with a timeout of 150 s per step, and then injects the next step.
**Rejected:** A fixed delay could reorder outcomes, and firing everything at once breaks the budget cases.

**Q:** Which scenarios?
**A:** Core trap cases, formats, security, and malware (EICAR).
**Decision:** The catalog has about 30 scenarios in 6 sections (see 05-demo-scenarios).

**Q:** Channel?
**A:** Fixed per scenario.
**Decision:** Each `DemoScenario.channel` is `"email"` or `"whatsapp"`. A few dedicated WhatsApp scenarios carry attachments.

**Q:** Language of simulated documents?
**A:** Each vendor's local language.
**Decision:** LatAm vendors write in Spanish, the BR vendor in Portuguese, and US/EU vendors in English.

**Q:** PDF realism?
**A:** Styled PDFs, which needs a new dependency.
**Decision:** `fpdf2` (pinned at install, which brings in Pillow) renders the invoices with a header, bill-to block, line-item table, totals and payment details. The "scanned" scenario is an image-only PDF rasterized with Pillow, so Textract has to OCR it.
**Rejected:** `minimal_pdf` was rejected because it looks fake on screen.

### 🏷️ Self-send kit (added mid-planning)

**Q:** Reviewers send scenario files from their own email or WhatsApp, so the sender is unknown and R05b would escalate. How should that be handled?
**A:** Demo trusted forwarders.
**Decision:** Add a new `trusted_forwarders` table (email or domain) owned by `payment_policy`. When the sender is on the list, sender identifiers are dropped from matching and R05b passes with "Forwarded by trusted forwarder …", so identity is judged from the document only. The seed adds `finance@andescape.com`. Reset keeps the table, the same way it keeps mailbox connections. Reviewers add their own address in the demo panel.
**Rejected:** "Expect escalations" weakens the happy-path story. "Trust the channel owner" weakens R05b.

**Q:** Where do reviewers get the files?
**A:** In the app, plus a kit in the repo.
**Decision:** Each scenario gets a "Files" download (`GET /demo/scenarios/{id}/kit`), and there is a full-kit download (`GET /demo/kit`) that includes a README with destinations and expected outcomes. `scripts/export_demo_kit.py` writes the same kit to `samples/demo-kit/`. Kit files use a fixed nonce (7000 + index), so they are deterministic and never collide with in-app launches. EICAR is never exported.

### 🏷️ Reset

**Q:** Reset scope?
**A:** Everything back to the initial seed.
**Decision:** Reset wipes the generated data and the policy, payees and blacklist, then re-seeds.

**Q:** Mailbox connections?
**A:** Keep them.
**Decision:** `mailbox_connections` rows are untouched. Their `inbox_emails` are deleted.

**Q:** In-flight runs?
**A:** Cancel them first.
**Decision:** `ExecutionRegistry` gains `owner_id` tracking and `cancel_owner(owner_id)`. Reset cancels and awaits the tasks in the demo sequencer, the inbox registry and the payments registry, in that order, before deleting anything.

### 🏷️ Ledger & executions

**Q:** Ledger rows?
**A:** Every outcome.
**Decision:** The ledger contains `payment_decisions` (agent and human) plus inbox-level terminal outcomes that have no bill (blocked, duplicate, no_invoice, no_info, error).

**Q:** Ledger organization?
**A:** One page with verdict tabs.
**Decision:** `/ledger` has the KPI strip, the charts, tabs (All / Paid / Escalated / Stopped), filters (period, payee, currency), CSV export, and rows that link to `/runs/[id]`.

**Q:** Chart library?
**A:** Recharts.
**Decision:** Add `recharts` (latest 3.x, React 19 compatible, exact version pinned) and theme it with DESIGN.md tokens.
**Rejected:** Hand-built SVG.

**Q:** Charts?
**A:** KPI strip, decisions over time, spend vs limits per payee, and top reasons with currencies.
**Decision:** All four are included.

**Q:** Execution detail depth?
**A:** Both the business summary and the full LLM trace, as two separate pages.
**Decision:** `/runs/[id]` shows the events timeline, the decision card, evidence and FX. `/runs/[id]/trace` shows the LangGraph checkpoint messages: system prompt, user message, AI turns, tool calls with args, and full tool outputs. The two pages link to each other.

**Q:** Runs list?
**A:** Yes.
**Decision:** `/runs` is a table of all runs, including failed and cancelled ones.

### 🏷️ FX

**Q:** FX source?
**A:** open.er-api.com with a static fallback.
**Decision:** Call `GET https://open.er-api.com/v6/latest/USD`, which needs no key and returns units per USD, then invert to get `usd_per_unit`. Attribution ("Rates By Exchange Rate API") is shown in the ledger footer. If CLF is missing from the response, the static table covers it.

**Q:** Rate date?
**A:** The decision date.
**Decision:** The rate is quoted when `register_bill` runs, i.e. "today", and stored on the bill. The payment copies it. Seeded history uses fixed per-month rates with `fx_source="seed"`.

**Q:** FX storage?
**A:** An `fx_rates` table, refreshed daily.
**Decision:** The new table `fx_rates` lives in the product DB. `bills` and `payments` get `fx_usd_per_unit`, `fx_rate_date` and `fx_source`.

**Q:** FX failure?
**A:** Static fallback, then review.
**Decision:** The lookup order is: live (2 s timeout), then the latest stored rate within 7 days, then the static table, then `None`. `None` leaves `amount_usd` null, and R09 sends the bill to review with "No exchange rate available for {CCY}".

**Q:** Limit currency?
**A:** Keep limits in USD.
**Decision:** All caps and budgets stay in USD. The UI shows each payee's local currency.

### 🏷️ Guardrail & language

**Q:** Guardrail misconfiguration?
**A:** Active by default, can be overridden, safe by default.
**Decision:** `GuardrailsSettings.enforce` defaults to `True`, and only an explicit `BLINKA_GUARDRAILS__ENFORCE=false` turns it off. The `.env` key typo is fixed.

**Q:** Missing guardrail ID?
**A:** Fail fast at startup.
**Decision:** The existing `_require_guardrail_id_when_enforced` validator now runs by default.

**Q:** UI language?
**A:** English, across the whole console.
**Decision:** All frontend copy moves to English (`lang="en"`, `en-US` Intl). Backend user-facing strings (phrases, rule reasons, explanations, checker questions, tool hints, agent todos and summaries) also move to English. Logs and HTTP details are already English.
