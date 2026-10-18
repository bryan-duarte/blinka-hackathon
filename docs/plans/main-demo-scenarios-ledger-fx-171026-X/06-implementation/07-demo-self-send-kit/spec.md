# Demo Self-send Kit & Trusted Forwarders Implementation

## Overview

Reviewers download the same PDF, ZIP and XML files the scenarios use, plus a ready-to-paste subject and body for the email-only cases, and send them from their own email or WhatsApp to the demo account's real channels.

The demo account keeps a **trusted forwarders** list. A finance inbox that forwards vendor documents is a common real-world setup. A sender on that list skips the "known sender" check (R05b), and their own address is not treated as an identifier of the payee, so the agent judges identity from the document alone.

## Files to Modify/Create

- `backend/modules/demo/kit.py` (new):
  - `KIT_NONCE_BASE = 7000`
  - `KitFile` dataclass
  - `scenario_kit_files(scenario, today) -> list[KitFile]`
  - `build_kit_zip(scenarios, today, destinations) -> bytes`
  - `render_kit_readme(scenarios, destinations) -> str`
- `backend/modules/demo/service.py`:
  - `scenario_kit(owner, scenario_id) -> bytes` (a ZIP for one scenario)
  - `full_kit(owner) -> bytes`
  - `kit_destinations() -> KitDestinations`
- `backend/contracts/demo.py`:
  - `KitDestinations(ApiModel)`: `email_address: str | None`, `whatsapp_number: str | None`.
  - `DemoScenarioView` gains `is_self_sendable: bool` (true when at least one step has an attachment or is body-only email) and `self_send_hint: str` (for example "Forward the PDF to {email}" or "Send the ZIP by WhatsApp to {number}").
  - `DemoCatalogView` gains `destinations: KitDestinations`.
- `backend/scripts/export_demo_kit.py` (new): `uv run python -m scripts.export_demo_kit [--out samples/demo-kit]`. It builds no DB or clients, only the catalog, renderers and settings for the destinations. It writes the folder layout below and overwrites `samples/demo-kit/`.
- Trusted forwarders, a general payment-policy feature (not demo-only), owned by the `payment_policy` module:
  - `backend/modules/payment_policy/models.py`: new table `trusted_forwarders(id UUID PK, owner_id FK users, kind String(16) "email"|"domain", normalized_value String, note String null, created_at)`, unique `(owner_id, kind, normalized_value)`.
  - `backend/contracts/payment_policy.py`: `TrustedForwarderKind(StrEnum)` (EMAIL, DOMAIN), `TrustedForwarderCreate(kind, value ≤200, note ≤120 | None)`, `TrustedForwarderView(forwarder_id, kind, normalized_value, note, created_at)`, plus `PayeeMatch.is_trusted_forwarder: bool = False`.
  - `backend/modules/payment_policy/repository.py`: `list_trusted_forwarders`, `add_trusted_forwarder` (`on_conflict_do_nothing`, which returns the existing row), `delete_trusted_forwarder`, `is_trusted_forwarder(owner_id, email, domain) -> bool`.
  - `backend/modules/payment_policy/service.py` and `clients/payment_policy.py`: mirror those methods.
  - `backend/modules/payment_policy/matching.py` `match_payee(...)`:
    - First resolve `is_trusted = await repository.is_trusted_forwarder(owner_id, sender_email, sender_domain)`. Check whether `match_payee` is sync; if it is, compute this in the service and pass it in.
    - When `is_trusted` is true, build the identifiers from the bill only (drop `sender_identifiers(sender)`), and set `is_trusted_forwarder=True`, `sender_email` and `sender_domain` on the `PayeeMatch`.
  - `backend/modules/payments/rules.py` `_known_sender`: if `match.is_trusted_forwarder` is true, return PASS with `f"Forwarded by trusted forwarder {match.sender_email}; identity checked from the document."`.
  - `backend/api/routers/payment_policy.py`: `GET /trusted-forwarders`, `POST /trusted-forwarders` (201), `DELETE /trusted-forwarders/{id}` (204), following the blacklist routes.
  - Migration: add the `trusted_forwarders` table. It can share the 02 migration if both land together; otherwise create its own revision.
- Seed (04): `DemoSeeder.seed` adds `finance@andescape.com` (email, note "Andescape finance inbox") so the `dup_forwarded` scenario keeps its meaning. **Reset (06) does not delete `trusted_forwarders`.** Seeding uses `add_trusted_forwarder`, which is idempotent, so the re-seed after a reset is safe.

## Implementation Guidelines

### Deterministic kit content

Kit files use `LaunchContext(today=export_day, nonce=KIT_NONCE_BASE + scenario_index)`. Because the nonce is fixed, invoice numbers are stable inside an exported kit and never collide with in-app launches, whose random nonce ranges from 1000 to 9999. Reuse the same `DemoStep.build` functions from 05, so the kit and the in-app send are always the same document.

### Kit layout (ZIP and `samples/demo-kit/`)

```text
demo-kit/
├── README.md                          # how to send, destinations, per-scenario table
├── 01-happy-path/
│   ├── happy_contractor_pdf/
│   │   ├── step-1-cuenta-de-cobro-lucia-hernandez.pdf
│   │   └── step-1-email.txt           # suggested subject + body (local language)
│   └── happy_saas_email/
│       └── step-1-email.txt           # body-only scenario: paste as the email body
├── 02-formats/
│   ├── format_xml_only/step-1-cfdi-agencia-brava.xml
│   ├── format_zip_xml_pdf/step-1-DTE-33-6201.zip
│   └── ...
├── 03-duplicates/dup_exact_resend/{step-1-…pdf, step-2-…pdf (same bytes), step-1-email.txt, step-2-email.txt}
...
└── 06-security/security_malware/README-malware.txt   # explains; the EICAR ZIP is NOT exported to the repo
```

- `step-N-email.txt` contains `Subject: …`, a blank line and then the body. Sender guidance in the README tells reviewers to send from an address registered as a trusted forwarder, or to add theirs in the demo panel (11).
- Scenarios that only make sense in-app are listed in the README as "in-app only", with the reason:
  - `security_malware`: the EICAR file is excluded from the repo export and from the download so it doesn't trip reviewers' antivirus or mail scanners. It is only sent from the in-app button.
  - `dup_against_history`: it depends on the seeded number, but it is still exportable.
  - `security_aws_impersonation` and `security_blacklisted_domain`: they rely on a specific spoofed sender, which a reviewer can't fake. The README says so and offers the in-app send.
- WhatsApp: only attachments can be sent, matching the existing pipeline. Body-only scenarios are marked email-only.

### README (`render_kit_readme`)

The README is in English. It contains:

1. A short intro: "Andescape Labs, Inc. pays a US + LatAm team. Send these files to the demo inbox and watch the agent decide."
2. Destinations: `destinations.email_address`, or "connect a Gmail in the console" when there is none, and `destinations.whatsapp_number`, with the note that the sender's phone must first be registered as the WhatsApp sandbox number in the console (existing `POST /inbox/whatsapp/sandbox` flow).
3. Trusted forwarders: how to add your address in the demo panel.
4. A table with columns # · Scenario · Files · Send via · Expected outcome · Key rules, built from `DemoExpectation`.
5. "Re-sending the same file is caught as a duplicate on purpose. Ask the presenter to reset the demo to start over."

### Destinations

`kit_destinations()` returns `email_address=settings.demo.inbox_address` and `whatsapp_number=settings.kapso.sandbox_display_number`. Inject both through `DemoService.__init__`.

### Dates in an exported repo kit

Due dates are export day + 15. An old export still works, because the rules don't reject overdue bills. Check this. If any rule does reject them, the README tells reviewers to download a fresh kit from the app. Re-export before the demo day.

## Dependencies

- 04 (renderers, seeder), 05 (catalog and step builders), 06 (reset leaves `trusted_forwarders` alone) and 01 (`DemoSettings.inbox_address`).

## Integration Notes

- 08 exposes `GET /demo/kit` and `GET /demo/scenarios/{scenario_id}/kit` (both `application/zip`, demo user only), plus the trusted-forwarder routes through the payment-policy router.
- 11 adds per-scenario "Download files" links, a "Download full kit" button, a destinations card, and a small trusted-forwarders editor in the panel.
- The 03 copy rule applies: the R05b PASS reason above is in English.
