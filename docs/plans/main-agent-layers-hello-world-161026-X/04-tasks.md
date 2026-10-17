# Implementation Tasks

## Task Breakdown

### 1. Prompts layer (`06-implementation/01-prompts`)
- [x] Create `contracts/prompts.py` with `PromptId`, `EmailMessage`, `EmailCategory`, `EmailPriority`, `EmailTriage` and `HelloWorldReport`.
- [x] Create `modules/prompts/base.py`, the `Prompt` ABC with `id`, `response_schema` and `get_text_prompt`.
- [x] Create `modules/prompts/errors.py` with `PromptsError`, `DuplicatePromptIdError`, `MissingPromptsError` and `MissingResponseSchemaError`.
- [x] Convert `main_agent.py` and `payment_agent.py` into `MainAgentPrompt` and `PaymentAgentPrompt`, keeping the text verbatim.
- [x] Move `modules/invoice_ingestor/prompts.py` to `modules/prompts/invoice_extraction.py` as `InvoiceExtractionPrompt` (`response_schema = InvoiceData`), then delete the old file.
- [x] Add `modules/prompts/email_triage.py` (`EmailTriagePrompt`, templated) and `modules/prompts/hello_world.py` (`HelloWorldPrompt`).
- [x] Add `modules/prompts/service.py`, containing `PromptsService` and the `PROMPTS` tuple.
- [x] Rewrite `modules/prompts/__init__.py`, removing `get_prompt` and `PromptName`.
- [x] Add `clients/prompts.py` with `PromptsClient`.

### 2. LLM layer (`06-implementation/02-llm-gateway`)
- [x] Update `LlmSettings` in `core/config.py` to the new fields and defaults.
- [x] Add `BearerAuthChatAnthropic` and rewrite `LlmGatewayService`: cached models, `model(kind)` and `default_model()`. Keep `extract()` as is.
- [x] Add `default_model()` to `clients/llm.py`.
- [x] In `pyproject.toml`, add `langchain-anthropic` and remove `langchain-openai`, then run `uv lock && uv sync`.
- [x] Update `backend/.env.example` with the new LLM keys and drop the Sonnet/Haiku 4.5 overrides.

### 3. Tools layer (`06-implementation/03-tools`)
- [x] Create `contracts/tools.py` with `RandomToken` and `SystemProfile`.
- [x] Create `modules/tools/hello_world.py` with the `@tool` functions `get_random_token` and `get_system_profile`.
- [x] In `ToolsService`, replace the docstring stub with `hello_world_tools() -> list[BaseTool]`.
- [x] In `ToolsClient`, replace the `list_tools` stub with `hello_world_tools()`.

### 4. Hello-world pipeline and wiring (`06-implementation/04-hello-world-pipeline`)
- [x] Add `MissingStructuredResponseError(AgentProviderError)` to `modules/orchestrator/errors.py`.
- [x] Add `prompts` and `tools` to the `OrchestratorService` constructor; change `_build_agent` to use `PromptsClient`; add `hello_world()`.
- [x] Add `hello_world()` to `clients/orchestrator.py`.
- [x] Update the payments agent and runner: `system_prompt` param and `PaymentRunDependencies.prompts`.
- [x] Inject `prompts` into the invoice ingestor service.
- [x] Update `container.py`: build prompts first, inject everywhere, add `Clients.prompts`.
- [x] Create `api/routers/diagnostics.py` and mount it publicly in `api/routers/__init__.py`.
- [x] Run `uv run ruff check . && uv run ruff format --check`.
- [x] Smoke run against real OpenRouter:
  1. Start the stack with `docker compose up` (DBs and MinIO) and the API with `pnpm dev`.
  2. Run `curl -X POST localhost:8000/diagnostics/hello-world`.
  3. Expect a 200 response with a non-empty `token`, `system_name == "blinka"`, and both tools listed in `tools_called`.
  4. Call it twice and confirm the tokens differ.

### Post-Implementation Quality Gate
- [x] Run a two-subagent quality pass over the change once it is applied:
  - [x] **Bug sweep:** launch a subagent to search the modified code for bugs, issues and inconsistencies (logic errors, edge cases, broken contracts, dead code, regressions). It reports concrete findings as `file:line` references.
  - [x] **Polish:** launch a subagent that invokes the `codebase-change` skill and applies the polish directly to the changed files. It deletes unnecessary comments, makes the code self-explanatory, gives every variable an obvious purpose, maximizes readability and maintainability, and removes unnecessary complexity. It also resolves any real issues the bug sweep surfaced.

## Task Order

```
1 Prompts ─┐
2 LLM ─────┼──► 4 Hello-world pipeline + wiring ──► smoke run ──► Quality gate
3 Tools ───┘
```

Tasks 1–3 are independent of each other. Task 4 needs all three. The app does not import cleanly until task 4's wiring is done, because the `get_prompt` removal breaks callers until they are updated.

## Deviations Applied

- **No `BearerAuthChatAnthropic` subclass and no Bearer header.** The plan overrode the private `_client_params` to add `Authorization: Bearer`. A live test showed that OpenRouter's Anthropic endpoint accepts the SDK's standard `x-api-key` header on its own, so the gateway builds plain `ChatAnthropic` instances in `_build_chat_model`. That removes the dependency on a private API, so the pin is `langchain-anthropic>=1.7` with no `<1.8` cap. It also keeps the key inside `SecretStr`: an earlier `default_headers` variant leaked the key through `repr()` and `model_dump()`, and the bug sweep caught it.
- **LLM-produced schemas use `ApiModel`, not `StrictModel`.** `ToolStrategy` (and `with_structured_output`) validate via `TypeAdapter.validate_python`, where strict mode rejects enum values given as strings; `EmailTriage` would never parse. `HelloWorldReport` is also the HTTP response model, which is `ApiModel`'s role.
- **Invoice PDF content block switched to the LangChain standard shape** (`{"type": "file", "base64", "mime_type", "filename"}`). The previous OpenAI `{"type": "file", "file": {...}}` shape is passed through unconverted by `ChatAnthropic`, which would break PDF invoice parsing after the provider switch. The standard block converts to an Anthropic `document` block (verified).
- **`MissingPromptsError` / `DuplicatePromptIdError` / `MissingResponseSchemaError` carry the offending ids** so the startup failure names what is wrong.
- **Smoke run** called `OrchestratorService.hello_world()` directly against OpenRouter (twice: distinct tokens, `system_name == "blinka"`, both tools called) instead of through `docker compose` + curl; the route was checked separately via the OpenAPI spec (public, `HelloWorldReport` response).
- **Phase 4 (Biome)** does not apply: the backend is Python. Ruff (`ruff check` + `ruff format --check`, the backend's `pnpm lint`) is the equivalent gate.
