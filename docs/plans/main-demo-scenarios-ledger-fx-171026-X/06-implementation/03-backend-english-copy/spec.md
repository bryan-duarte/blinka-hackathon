# Backend English Copy Implementation

## Overview

Every user-facing string the backend produces is translated to English: agent phrases, rule reasons, explanations, checker questions, tool hints, budget scope labels and the prompt instructions that set the language of todos and summaries. Identifiers, logs and HTTP `detail` messages are already English and stay as they are.

## Files to Modify/Create

- `backend/modules/payments/phrases.py`: translate every phrase pool (tool start/finish, per step). Keep the random-choice structure.
- `backend/modules/payments/rules.py`:
  - Translate every `rule_result(...)` reason string and constant (`NO_USD_AMOUNT_REASON` and the others).
  - Rename the `RULE_NAMES` values to English snake_case, keeping the IDs:

    | ID | New name |
    |---|---|
    | R01 | `complete_data` |
    | R02 | `no_embedded_instructions` |
    | R03 | `not_blacklisted` |
    | R04 | `registered_payee` |
    | R05 | `consistent_identity` |
    | R05b | `known_sender` |
    | R06 | `kind_matches` |
    | R07 | `category_allowed` |
    | R08 | `category_confident` |
    | R09 | `currency_allowed` |
    | R11 | `no_probable_duplicate` |
    | R12 | `hard_cap` |
    | R13 | `auto_pay_limit` |
    | R14 | `budget_available` |
    | R17 | `matches_agreement` |
    | R18 | `tax_identity_consistent` |
    | CHK1 | `checker_identity` |
    | CHK2 | `checker_amount` |
    | CHK3 | `checker_history` |
    | DUP | `exact_duplicate` |
    | PAY | `payment_execution` |
    | ERR | `technical_error` |

    For CHK1–CHK3, adjust the names to match the actual meaning in `checker.py`.
  - Translate the evidence dict keys that are Spanish (e.g. `"factura_previa"` becomes `"previous_bill"`).
  - Change the date formats in reasons from `%d-%m` to `%b %d`.
- `backend/modules/payments/explain.py`: write the explanation sentences in English. The FX line format is in 02-fx-conversion.
- `backend/modules/payments/budget.py` `describe_scope`: returns `"global monthly"`, `"{category} monthly"` or `"{payee.display_name} monthly"`.
- `backend/modules/payments/settlement.py`: translate the reason strings (`UNPAYABLE_REASON`, `"Presupuesto … agotado al reservar el pago."` becomes `"{scope} budget exhausted while reserving the payment."`, plus the duplicate and fail-closed reasons).
- `backend/modules/payments/checker.py`: translate the question texts and any rationale templates.
- `backend/modules/payments/agent_tools.py`: translate the `TOOL_DESCRIPTIONS` and every `_out_of_order` hint.
- `backend/modules/prompts/payments_agent.py`: change the instruction "write todos and summaries in Spanish" to English. Translate any Spanish example text.
- `backend/modules/prompts/payment_checker.py`, `candidate_extraction.py`, `bill_classification.py`: make sure every requested free-text output (reason, rationale) is in English. Extraction must still read documents in any language. Add the line "Documents may be in Spanish, Portuguese or English; always answer in English."
- `backend/modules/inbox/pipeline.py` / `notifier.py` / `service.py`: translate any user-facing `error` strings or messages stored in `inbox_emails.error` or published as `message`.
- `backend/modules/guardrails/service.py`: translate the `GuardrailViolation.message` texts if they are Spanish.
- `backend/modules/files/*`: translate the user-facing intake reasons if they are Spanish.

## Implementation Guidelines

- Find every remaining string with `rg -n "[áéíóúñ¿¡]" backend/modules backend/contracts`, and also look for common Spanish words (`" de "`, `"factura"`, `"pago"`, `"presupuesto"`, `"monto"`). Translate every hit except the demo documents (`modules/demo/catalog.py` and the seed data), which stay in each vendor's language on purpose.
- `fx.EXPLICIT_CURRENCY_MARKERS` holds Spanish document vocabulary, not UI copy. Keep it, and add English markers where they are missing (`"pesos"` stays as is, add `"euros"`).
- Tone: short and factual, e.g. `"USD 1,470.00 exceeds the auto-pay limit of USD 1,000.00; a person must approve."`
- Keep `format_usd` output `USD 1,234.56`, and check that its thousands separator is `,`.

## Dependencies

None. This can run in parallel with 02. When both touch the same reason line (R09), use the English text from this spec.

## Integration Notes

- The frontend's `RULE_LABELS` (if present in `labels.ts`) must be keyed by rule ID, not by name, so this rename has no effect there. Check this in 10.
- Existing tests that assert Spanish strings will need their literals updated. That is a mechanical fix.
