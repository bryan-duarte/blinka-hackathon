# User Preferences & Decisions

## 👤 Configuration Preferences

- **Context Level**: Moderado
- **Participation Level**: Equilibrado
- **Detail Level**: Neutral (snippets are orientative; implementer decides final code)

## 💬 Q&A and Rationale

### 🏷️ LLM layer
**Q:** Align the LLM client with the reference (`BearerAuthChatAnthropic` → OpenRouter Anthropic endpoint) or keep `ChatOpenAI`?
**A:** Replace with ChatAnthropic.
**Decision:** Port `BearerAuthChatAnthropic` into `modules/llm_gateway/service.py`. Every model consumer (orchestrator chat, payments agent, invoice `extract`, hello-world) uses it. Add `langchain-anthropic`, remove `langchain-openai`.
**Rejected:** Keeping ChatOpenAI diverges from the reference; running both clients side by side doubles maintenance.

**Q:** Model configuration?
**A:** Single default plus per-kind override.
**Decision:** `BLINKA_LLM__MODEL` defaults to `anthropic/claude-haiku-5.5`. `main_model` and `payments_model` become `str | None = None` and fall back to `model`. Build one cached chat model per distinct model name at construction.
**Rejected:** Keeping only per-kind fields adds a kind per use case; Haiku 4.5 is outdated.

### 🏷️ Prompts layer
**Q:** What happens to existing string prompts and `get_prompt()`?
**A:** Migrate everything to classes.
**Decision:** `main_agent`, `payment_agent` and `invoice_ingestor/prompts.py::INVOICE_EXTRACTION_PROMPT` become `Prompt` subclasses. `get_prompt`, `PromptName` and `modules/invoice_ingestor/prompts.py` are deleted. Callers use `PromptsClient`.
**Rejected:** Running two prompt patterns side by side.

**Q:** How is the optional response schema exposed?
**A:** As a ClassVar attribute.
**Decision:** `id: ClassVar[PromptId]` and `response_schema: ClassVar[type[BaseModel] | None] = None`.
**Rejected:** Abstract `schema()` methods, which add boilerplate for prompts that have no schema.

**Q:** How do templated prompts receive variables?
**A:** Through `get_text_prompt(**variables)` on stateless registry singletons.
**Decision:** The method is named **`get_text_prompt`**, as the user chose. `EmailTriagePrompt.get_text_prompt(*, email: EmailMessage)`. Prompts without variables take none. `PromptsClient.get_text_prompt(prompt_id, **variables)`.
**Rejected:** Constructor-injected variables, which break the singleton registry.

**Q:** Prompt names?
**A:** `EmailTriagePrompt` and `HelloWorldPrompt`.
**Decision:** The `PromptId` members are `MAIN_AGENT`, `PAYMENT_AGENT`, `INVOICE_EXTRACTION`, `EMAIL_TRIAGE` and `HELLO_WORLD`.

### 🏷️ Email prompt
**Q:** What does the email prompt analyze?
**A:** Generic triage.
**Decision:** The schema `EmailTriage` has these fields: `category`, `priority`, `summary`, `action_items`, `requires_reply`.
**Rejected:** Payment-specific extraction, and triage combined with payment details.

**Q:** How does email content reach the prompt?
**A:** Through a templated `get_text_prompt(email=...)`.
**Decision:** The template interpolates `sender`, `subject`, `received_at` and `body` inside `<email>` delimiters, and tells the model to treat that content as data.

### 🏷️ Tools layer
**Q:** Which dummy tools?
**A:** A random token tool and a fixed profile tool.
**Decision:** `get_random_token()` returns `{"token", "generated_at"}`. `get_system_profile()` returns a fixed `SystemProfile`.

**Q:** Tool definition style?
**A:** The `@tool` decorator.
**Decision:** Module-level `@tool("<name>")` async functions in `modules/tools/hello_world.py`, matching `modules/payments/agent.py`. `ToolsService.hello_world_tools()` returns them.
**Rejected:** The reference's `StructuredTool.from_function`.

### 🏷️ Hello-world pipeline
**Q:** How is the tool execution verified?
**A:** Trust the agent's answer.
**Decision:** The endpoint returns the agent's `HelloWorldReport` as is, with no server-side comparison against the ToolMessages.

**Q:** Endpoint path and access?
**A:** `POST /diagnostics/hello-world`, public.
**Decision:** A new `diagnostics_router`, mounted without `get_current_user`.

**Q:** Who owns the run?
**A:** `OrchestratorService.hello_world()`.
**Decision:** It mirrors the reference `greet()`, uses no checkpointer, and its errors map to the existing 503 handler.
**Rejected:** A new diagnostics module, which adds wiring for a single method.

### 🏷️ Agent-decided (not asked)
- `HelloWorldReport` is returned directly as the response model, like the reference `Greeting`. No extra ApiModel wrapper.
- `ModelKind` stays `Literal["main", "payments"]`. Hello-world uses `default_model()`.
- `LlmGatewayService.extract()` keeps its JSON-mode fallback unchanged, because the fallback is provider-agnostic.
- `MissingStructuredResponseError` subclasses `AgentProviderError`, so it reuses the 503 mapping.
- The unused `contracts/llm.py::ModelSpec` is left untouched. It is pre-existing dead code and is only mentioned, not removed.
