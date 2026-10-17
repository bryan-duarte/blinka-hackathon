# Risks & Mitigations

## Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| The OpenRouter Anthropic endpoint rejects the `x-api-key` auth that `ChatAnthropic` sends | high | Use `BearerAuthChatAnthropic`, which overrides the `_client_params` cached_property (it exists in langchain-anthropic 1.7.6, `chat_models.py:1739`) to add `Authorization: Bearer`. Set `base_url` to `https://openrouter.ai/api` without `/v1`, because the SDK appends `/v1/messages`. |
| The model id `anthropic/claude-haiku-5.5` is not available on OpenRouter for this account | med | It is overridable through `BLINKA_LLM__MODEL`. The smoke run surfaces the problem as a 503 `agent provider unavailable` with a logged `hello_world_agent_failed` exception. |
| Haiku skips a tool or invents the token instead of calling `get_random_token` | med | The prompt explicitly requires both tool calls and an exact copy of the token. Calling the endpoint twice and getting different tokens is a strong hint that the tool really ran. A server-side check was declined by the user, so this stays a manual check. |
| `StrictModel` (`strict=True`) rejects a `ToolStrategy` payload | med | Schema fields are restricted to `str`, `bool`, `list[str]` and `StrEnum`, with no `datetime` or `UUID` in LLM-produced schemas. |
| The private `_client_params` changes in a future langchain-anthropic version | low | Pin `langchain-anthropic>=1.7,<1.8`. |

## Integration Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Removing `get_prompt` and `invoice_ingestor/prompts.py` breaks imports in the orchestrator, payments and invoice ingestor | high | Task 4 updates all three call sites, which `grep` confirms are the only ones. Run `uv run python -c "import api.app"` after the wiring is done. |
| A local `backend/.env` still sets `BLINKA_LLM__MAIN_MODEL=anthropic/claude-sonnet-4.5` and `BLINKA_LLM__BASE_URL=.../api/v1` | med | Update `.env.example`. Tell the user to remove the old `MAIN_MODEL`/`PAYMENTS_MODEL` lines from `.env` if they want Haiku everywhere. An OpenAI-style `/api/v1` base URL breaks the Anthropic client. |
| Switching the chat and payments agents from Sonnet to Haiku changes their behaviour | med | Intentional, at the user's request. Per-kind overrides restore Sonnet without any code change. |
| `invoice_ingestor.extract()` moves to Anthropic structured output | low | `with_structured_output` on ChatAnthropic uses tool calling. The JSON-mode fallback is provider-agnostic and stays. |
| The public endpoint spends LLM tokens on every call | low | Accepted for the hackathon. It is easy to move under `get_current_user` later. |

## Edge Cases Identified

- **The agent does not produce `structured_response`, or produces the wrong type:** raise `MissingStructuredResponseError` (a subclass of `AgentProviderError`), which maps to 503.
- **The provider raises a network, auth or rate-limit error:** wrap it in `AgentProviderError` with `logger.exception("hello_world_agent_failed")`, which maps to 503.
- **The email body contains `{` or `}`:** `str.format` only treats braces in the template as placeholders, not braces inside the substituted values, so this is safe. The template itself must not contain literal braces.
- **The email contains instructions aimed at the model (prompt injection):** wrap the email in `<email>` tags and state that its contents are data and never instructions.
- **`get_text_prompt` is called without the required variables:** Python raises a `TypeError`, which is a programmer error, so no extra handling is added.
- **The registry is missing a `PromptId`:** `PromptsService.__init__` raises `MissingPromptsError` at startup, so the problem fails fast in the lifespan.
