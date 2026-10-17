# Payments → CLP Analysis Agent (TEMPORAL) Implementation

## Overview

This repurposes the payment agent. Instead of executing a stub payment, it reads the parsed invoice, converts the total to CLP with dummy rates, and returns a structured `InvoiceClpAnalysis`. Every repurposed spot carries a `# TEMPORAL:` comment, as the user asked.

## Files to Modify/Create

- `backend/contracts/payments.py`: add `ClpConversion` and `InvoiceClpAnalysis`, and add `analysis: InvoiceClpAnalysis | None = None` to `PaymentRunStatus`. Field lists are in `03-design.md`.
- `backend/modules/payments/agent.py`: add `DUMMY_CLP_RATES` and the `convert_to_clp` tool, change the tool list, and add `response_schema` → `ToolStrategy`.
- `backend/modules/payments/runner.py`: in `_pay_invoice`, read the structured response, and change `_seed_message` to the new wording.
- `backend/modules/payments/errors.py`: add `MissingAnalysisError(PaymentsError)`.
- `backend/modules/payments/service.py`: in `get_run`, fill `analysis`.
- `backend/modules/prompts/payment_agent.py`: new prompt text and `response_schema = InvoiceClpAnalysis`.
- `backend/modules/prompts/invoice_extraction.py`: add the Chilean rules.

## Implementation Guidelines

These snippets are orientative.

### `agent.py`

```python
# TEMPORAL: dummy rates to test the email → CLP pipeline; replace with a real FX source.
DUMMY_CLP_RATES = {"CLP": 1.0, "USD": 950.0, "EUR": 1030.0, "CLF": 39_500.0}


@tool
async def convert_to_clp(amount: float, currency: str) -> dict:
    """Convert an amount in the given ISO 4217 currency (UF is CLF) to Chilean pesos."""
    clp_rate = DUMMY_CLP_RATES.get(currency.upper())
    if clp_rate is None:
        return {"error": f"unsupported currency {currency}"}
    conversion = ClpConversion(amount=amount, currency=currency.upper(), clp_rate=clp_rate,
                               amount_clp=round(amount * clp_rate))
    return conversion.model_dump()


# TEMPORAL: not wired while the payment agent only analyzes invoices in CLP.
@tool
async def execute_payment(...): ...   # unchanged


def build_payment_agent(llm, payments_checkpointer, invoice, system_prompt,
                        response_schema: type[BaseModel]) -> CompiledStateGraph:
    # TEMPORAL: analysis-only toolset; restore execute_payment to execute payments again.
    tools = [build_invoice_context_tool(invoice), convert_to_clp]
    return create_deep_agent(model=llm, system_prompt=system_prompt, tools=tools,
                             checkpointer=payments_checkpointer,
                             response_format=ToolStrategy(response_schema))
```

### `runner.py::_pay_invoice`

Keep the name and the event sequence. Only the tail changes:

```python
agent = build_payment_agent(
    dependencies.llm_gateway.model("payments"), dependencies.payments_checkpointer, invoice,
    dependencies.prompts.get_text_prompt(PromptId.PAYMENT_AGENT),
    dependencies.prompts.get_response_schema(PromptId.PAYMENT_AGENT),
)
agent_state = await agent.ainvoke(...)          # unchanged
analysis = agent_state.get(STRUCTURED_RESPONSE_KEY)
if not isinstance(analysis, InvoiceClpAnalysis):
    raise MissingAnalysisError
await repository.insert_event(run_id, "completed",
                              {"summary": analysis.summary, "analysis": analysis.model_dump(mode="json")})
await repository.update_status(run_id, RunStatus.COMPLETED)
await _record_execution(dependencies, owner, session_id, invoice, analysis.summary)
```

- Define `STRUCTURED_RESPONSE_KEY = "structured_response"` locally, as in `modules/orchestrator/service.py:42`.
- `MissingAnalysisError` falls into the generic `except Exception` branch, which records the `failed` event and sets status `FAILED`.
- Change `_seed_message` (with a `# TEMPORAL:` comment) to:
  ```python
  "Analyze the following invoice and report its total in CLP. Invoice data:\n" + invoice.model_dump_json()
  ```

### `service.py::get_run`

```python
events = await self._repository.list_events(run_id)
return PaymentRunStatus(run_id=..., status=..., error=..., events=events,
                        analysis=_latest_analysis(events))
```

`_latest_analysis(events)` walks the events in reverse, finds the first with `step == "completed"` and `"analysis" in payload`, and returns `InvoiceClpAnalysis.model_validate(payload["analysis"])`. If there is none, it returns `None`.

### `payment_agent.py`

```python
# TEMPORAL: the payment agent only analyzes invoices in CLP to test the email pipeline.
PAYMENT_AGENT_PROMPT = """You are Blinka's invoice analysis agent. You run unattended in the
background: no user will answer questions, so never ask any.

You receive one invoice's data. Use `get_invoice_context` to read it. Decide whether it is a
real invoice (vendor, number and a positive total). If it is, call `convert_to_clp` exactly once
with the invoice total and currency (use CLF for UF), and copy its clp_rate and amount_clp into
your answer. Never compute CLP amounts yourself.

Finish by calling the response tool exactly once. Write `summary` in Spanish, one or two
sentences, e.g. "Factura 123 de ACME por USD 120,00 ≈ CLP 114.000.". If the data is not an
invoice, set is_invoice to false, leave the amounts empty and explain why in summary.
"""


class PaymentAgentPrompt(Prompt):
    id = PromptId.PAYMENT_AGENT
    response_schema = InvoiceClpAnalysis
```

### `invoice_extraction.py`

Append these lines to the rules:

```
- Chilean invoices (factura/boleta): currency is "CLP"; "." is the thousands separator and "," the
  decimal separator (e.g. "$114.000" is 114000); total_amount is the final total including IVA.
- Amounts in UF use currency "CLF".
```

## Dependencies

- `langchain.agents.structured_output.ToolStrategy`, already used in `modules/orchestrator/service.py`.
- `PromptsClient.get_response_schema`.

## Integration Notes

- `PaymentRunTrigger`, `start_run` and `run_execution` keep their signatures. The inbox (spec 05) starts runs with `PaymentRunTrigger(file_id=..., session_id=None)`.
- Contract for the inbox:
  - `PaymentRunStatus.status == COMPLETED` → `analysis` is set.
  - `FAILED` with an event `step == "invoice_parse_failed"` → no invoice.
- The chat `initiate_payments` tool now yields this analysis too. That is expected while the change is TEMPORAL.
