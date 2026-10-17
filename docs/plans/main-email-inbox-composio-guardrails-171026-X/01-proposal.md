# Email Inbox Layer: Composio → Bedrock Guardrails → CLP Agent

> "Finally, an inbox that reads your invoices, refuses to be sweet-talked by them, and tells you in pesos how broke you are."
> - El Barto

## Overview

**Request**: Plan the first layer of email analysis. The user connects Gmail or Outlook through OAuth2 using Composio. A Composio trigger fires on each new email. The email goes through a Bedrock Guardrails check (prompt injection and similar attacks). If it passes, the payment subagent runs as a background job, analyzes the bill and answers with the amount in CLP. A temporary frontend shows an OAuth connect button, an inbox, and the agent's answer for each email. Everything is dummy-grade, built only to test the pipeline.

**Created**: 2026-10-17

## What

- **Mailbox connection:** the user logs in with the existing email/password JWT. The UI then offers "Connect Gmail" and "Connect Outlook" buttons. These go through Composio-managed OAuth (`connected_accounts.link`). After that, a new-mail trigger is enabled for the account.
- **Event ingestion:** a public `POST /webhooks/composio` endpoint. It verifies the Composio signature, stores the email, and starts a background pipeline. In local development, the Composio CLI forwards the events to this endpoint.
- **Guardrails:** the existing `GuardrailsService` stub becomes a real Amazon Bedrock `ApplyGuardrail` call (Standard tier, PROMPT_ATTACK set to HIGH). It checks the subject, the body and the text of any PDF attachment. A bootstrap script creates the guardrail using the `panoptico` AWS profile.
- **CLP analysis (TEMPORAL):**
  - The payment agent is repurposed. Instead of executing a stub payment, it reads the invoice and returns a structured `InvoiceClpAnalysis`.
  - Conversion uses a static table of dummy rates.
  - Every changed spot is marked with a `# TEMPORAL` comment.
- **Inbox UI:** Next.js pages for login, the inbox (connections, email list, detail view) and the OAuth callback. The inbox polls every 4 seconds. A "Simulate email" button injects sample invoice, injection and plain emails, so you don't have to wait out Gmail's 15-minute polling.

## Why

The product needs to react to real invoices arriving by email. Composio covers mailbox OAuth and change detection, and Bedrock Guardrails screens untrusted email text before any agent reads it. This layer proves the full path end to end (provider → guardrail → background agent → UI) before any real payment logic exists.

## Impact

- **Backend:**
  - New modules: `mail_gateway` (Composio) and `inbox` (tables, pipeline, samples).
  - Real Bedrock guardrails.
  - Repurposed payment agent.
  - New routers: `/inbox/*` and `/webhooks/composio`.
  - CORS middleware.
  - New `product` migration.
  - Two bootstrap scripts.
- **Frontend:** goes from a placeholder to a working 3-page app.
- **Behaviour change:** the chat → `initiate_payments` flow now produces a CLP analysis instead of a "payment executed" message. This is temporary.

## Flow

```
 Gmail / Outlook ──(Composio trigger)──► composio dev listen --forward (dev)
                                                │
                                                ▼
                               POST /webhooks/composio  (signature verified)
                                                │ insert inbox_emails(RECEIVED), dedupe
                                                ▼
          "Simulate email" button ───► InboxService ──spawn──► process_email (background)
                                                                  │ 1 fetch content (Composio tools)
                                                                  │ 2 store PDF / body as file
                                                                  │ 3 Bedrock ApplyGuardrail
                                                                  ├── blocked ──► BLOCKED (+violations)
                                                                  ▼ allowed
                                                       payments.start_run(file_id)  ──► ANALYZING
                                                                  │ (existing ExecutionRegistry)
                                                                  ▼
                                    invoice_ingestor.parse → payment agent (TEMPORAL)
                                    convert_to_clp tool → InvoiceClpAnalysis
                                                                  │
 Next.js /inbox  ◄──── GET /inbox/emails (poll 4s) ◄── ANALYZED / NO_INVOICE / ERROR
```
