# LLM Gateway & Prompts

## Overview

The ONLY place chat models are constructed. Currently OpenRouter via `ChatOpenAI(base_url=...)`; swappable later without touching agents. Prompts module is a static registry of agent system prompts.

## Files to Create

- `backend/modules/llm_gateway/__init__.py` — facade: `LlmGatewayService`, `ModelNotConfiguredError`
- `backend/modules/llm_gateway/errors.py` — `ModelNotConfiguredError` (unknown `ModelSpec.kind`)
- `backend/modules/llm_gateway/service.py`:

```python
class LlmGatewayService:
    def __init__(self, settings: LlmSettings) -> None: ...

    def model(self, kind: Literal["main", "payments"]) -> BaseChatModel:
        # name = settings.main_model if kind == "main" else settings.payments_model
        # return ChatOpenAI(model=name, base_url=settings.base_url,
        #                   api_key=settings.api_key.get_secret_value(), temperature=0)
```

- `backend/clients/llm.py` — `LlmGatewayClient.model(kind)` (same signature; sync method is fine — construction is cheap and stateless).
- `contracts/llm.py` — `ModelSpec` per 03-design.md (kept as the seam even if the client takes a Literal for now).
- `backend/modules/prompts/__init__.py` — registry: `get_prompt(name: Literal["main_agent", "payment_agent"]) -> str`, `__all__`.
- `backend/modules/prompts/main_agent.py` — `MAIN_AGENT_PROMPT`: conversational assistant for Blinka; can start invoice payments via the `initiate_payments` tool when the user provides an invoice file or data; must surface the returned run id to the user.
- `backend/modules/prompts/payment_agent.py` — `PAYMENT_AGENT_PROMPT`: executes invoice payment end-to-end, reports progress as it goes, never asks the chat user questions (runs unattended).

## Implementation Guidelines

- Keep `temperature=0` default; agents are task-execution oriented.
- No caching of model instances beyond trivial memoization if desired — instances are cheap.
- When the provider changes (user: "later we gonna change this"), only this module edits.

## Dependencies

02-backend-skeleton (settings).

## Integration Notes

`orchestrator` calls `model("main")`; `payments/agent.py` calls `model("payments")`; `invoice_ingestor` uses `model("main")` for extraction. Prompt names are referenced by those modules — keep the Literal values stable.
