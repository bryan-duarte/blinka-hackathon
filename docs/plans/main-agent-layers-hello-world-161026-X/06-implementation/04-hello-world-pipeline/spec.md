# Hello-World Pipeline & Wiring Implementation

## Overview

`OrchestratorService.hello_world()` runs a one-shot deep agent that uses the hello-world prompt, the dummy tools and `ToolStrategy(HelloWorldReport)`. It is exposed at `POST /diagnostics/hello-world`, which is public. The same change moves every existing prompt consumer onto `PromptsClient` and updates `container.py`.

## Files to Modify/Create

All paths are under `backend/`.

- **`modules/orchestrator/errors.py`**: add `class MissingStructuredResponseError(AgentProviderError): pass`.
- **`modules/orchestrator/service.py`**:
  - The constructor gains `prompts: "PromptsClient"` and `tools: "ToolsClient"`, both as `TYPE_CHECKING` imports.
  - `_build_agent` uses `self._prompts.get_text_prompt(PromptId.MAIN_AGENT)`.
  - Add `async def hello_world(self) -> HelloWorldReport`.
  - Remove the `from modules.prompts import get_prompt` import.
- **`clients/orchestrator.py`**: add `async def hello_world(self) -> HelloWorldReport`.
- **`modules/payments/agent.py`**:
  - `build_payment_agent(llm, payments_checkpointer, invoice, system_prompt: str)` passes `system_prompt=system_prompt`.
  - Remove the `get_prompt` import.
- **`modules/payments/runner.py`**:
  - `PaymentRunDependencies` gains `prompts: "PromptsClient"`.
  - `_pay_invoice` passes `dependencies.prompts.get_text_prompt(PromptId.PAYMENT_AGENT)` to `build_payment_agent`.
- **`modules/invoice_ingestor/service.py`**:
  - The constructor gains `prompts: "PromptsClient"`.
  - `_extract_invoice` uses `system=self._prompts.get_text_prompt(PromptId.INVOICE_EXTRACTION)`.
  - Remove the `INVOICE_EXTRACTION_PROMPT` import.
- **`container.py`**:
  - Import `PromptsClient`, `PROMPTS` and `PromptsService`.
  - Add `prompts: PromptsClient` to `Clients`.
  - Build `prompts = PromptsClient(PromptsService(PROMPTS))` next to `llm`.
  - Pass `prompts` to `InvoiceIngestorService(...)`, `PaymentRunDependencies(...)` and `OrchestratorService(...)`.
  - Pass `tools` to `OrchestratorService(...)`.
  - Include `prompts=prompts` in the returned `Clients(...)`.
- **`api/routers/diagnostics.py`** (new): `diagnostics_router`.
- **`api/routers/__init__.py`**: import `diagnostics` and add `api_router.include_router(diagnostics.diagnostics_router)`, with no auth dependency.

## Implementation Guidelines

The snippets below are orientative.

```python
# modules/orchestrator/service.py
STRUCTURED_RESPONSE_KEY = "structured_response"

async def hello_world(self) -> HelloWorldReport:
    task = self._prompts.get_text_prompt(PromptId.HELLO_WORLD)
    report_schema = self._prompts.get_response_schema(PromptId.HELLO_WORLD)
    agent = create_deep_agent(
        model=self._llm.default_model(),
        tools=self._tools.hello_world_tools(),
        response_format=ToolStrategy(report_schema),
    )
    try:
        agent_state = await agent.ainvoke({"messages": [HumanMessage(content=task)]})
    except Exception as agent_error:
        logger.exception("hello_world_agent_failed")
        raise AgentProviderError from agent_error
    report = agent_state.get(STRUCTURED_RESPONSE_KEY)
    if not isinstance(report, HelloWorldReport):
        raise MissingStructuredResponseError
    logger.info("hello_world_completed", tools_called=report.tools_called)
    return report
```

- Import `ToolStrategy` with `from langchain.agents.structured_output import ToolStrategy`.
- Pass no checkpointer and no `system_prompt`, because the task goes in as the user message, the way the reference `greet()` does it.
- Check `isinstance` against the concrete `HelloWorldReport`, so the return type is honest.

```python
# api/routers/diagnostics.py
diagnostics_router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@diagnostics_router.post("/hello-world", response_model=HelloWorldReport)
async def hello_world(clients: ClientsDep) -> HelloWorldReport:
    return await clients.orchestrator.hello_world()
```

Expected response:

```json
{
  "greeting": "Hello from Blinka!",
  "token": "9f2c4e1ab37d0c55",
  "token_generated_at": "2026-10-16T14:03:11.204Z",
  "system_name": "blinka",
  "tools_called": ["get_system_profile", "get_random_token"]
}
```

Error paths map through the existing `api/app.py::_reject_agent_provider_down` handler, so both provider failures and a missing structured response return 503 `{"detail": "agent provider unavailable"}`.

## Dependencies

- Module 01: `PromptsClient`, `PromptId`, `HelloWorldReport`, `PROMPTS`, `PromptsService`.
- Module 02: `LlmGatewayClient.default_model()`.
- Module 03: `ToolsClient.hello_world_tools()`.
- `deepagents.create_deep_agent` (0.7.28, accepts `response_format`) and `langchain.agents.structured_output.ToolStrategy` (langchain 1.4.6).

## Integration Notes

- Verify by running `uv run python -c "import api.app"` and `uv run ruff check . && uv run ruff format --check`.
- For the smoke test, start the DBs and MinIO, because the lifespan needs them even though this endpoint doesn't. Then run `curl -sX POST localhost:8000/diagnostics/hello-world | jq`. Run it twice: the tokens should differ.
- If an existing `backend/.env` sets `BLINKA_LLM__MAIN_MODEL`, `BLINKA_LLM__PAYMENTS_MODEL` or a `/api/v1` base URL, remove those lines.
