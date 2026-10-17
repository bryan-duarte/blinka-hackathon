# Technical Design

All paths are relative to `backend/`.

## Architecture Decisions

1. **Prompts are a registry of stateless `Prompt` singletons.** `PromptsService` indexes them by `PromptId` and validates at construction: duplicate ids raise an error, and every `PromptId` member must be registered. `PromptsClient` is the only way other modules reach prompts.
2. **Prompt text comes from `get_text_prompt(**variables) -> str`.** Prompts without variables return a constant. Templated prompts declare keyword-only parameters and format a module-level template.
3. **The optional response schema is a ClassVar.** `response_schema: ClassVar[type[BaseModel] | None] = None`. `PromptsClient.get_response_schema(id)` raises `MissingResponseSchemaError` when the schema is `None`.
4. **The LLM gateway builds `BearerAuthChatAnthropic` instances once, at construction.** It keeps one instance per distinct model name. `model(kind)` returns the override for that kind, or the default. `default_model()` returns the default.
5. **Tools are module-level `@tool` async functions.** They are grouped into toolsets by `ToolsService`, and `ToolsClient` exposes them as `list[BaseTool]`.
6. **The hello-world agent is a one-shot deep agent.** It is built with `create_deep_agent(..., response_format=ToolStrategy(schema))` and has no checkpointer. The prompt text is sent as the user message, as in the reference `greet()`.
7. **`/diagnostics/hello-world` is public** and returns `HelloWorldReport` directly.

## Patterns & Conventions

- Module layout and facade: follow `modules/files/__init__.py`, which re-exports public names with an alphabetized `__all__`.
- Client facade: follow `clients/orchestrator.py`. Import the service only under `TYPE_CHECKING` and use string annotations.
- Errors: follow `modules/auth/errors.py`. Use a bare base class `PromptsError(Exception): pass` and `pass` subclasses. Wrap third-party errors with `raise X from error`, as `modules/orchestrator/service.py::chat` does.
- Logging: `logger = get_logger(__name__)` with snake_case events, e.g. `logger.exception("hello_world_agent_failed")`.
- Constants are module-level UPPER_SNAKE values: `HELLO_WORLD_TASK`, `EMAIL_TRIAGE_TEMPLATE`, `STRUCTURED_RESPONSE_KEY`.
- No `#` comments. The only docstrings are tool descriptions and schema docstrings, which `ToolStrategy` turns into tool descriptions.
- Contracts:
  - Internal schemas use `StrictModel` (`contracts/_base.py`).
  - `StrEnum` members are UPPER_SNAKE with lowercase values (`contracts/files.py::FileParseStatus`).
- Tools: follow `modules/payments/agent.py::execute_payment`, an `@tool` async function with a docstring.
- Router: follow `api/routers/chat.py`. Use `ClientsDep`, `response_model=`, and repeat the response type as the return annotation.
- `container.py` is the only place services are instantiated.

## Dependencies

- Add `langchain-anthropic>=1.7`. It is already locked at **1.7.6** as a transitive dependency of `deepagents`, so this declares it directly.
- Remove `langchain-openai>=1.0`. After the gateway change nothing imports it.
- Already available: `deepagents` 0.7.28 (`create_deep_agent` accepts `response_format`) and `langchain` 1.4.6 (`langchain.agents.structured_output.ToolStrategy`).
- Run `uv lock` and `uv sync` after editing `pyproject.toml`.

## Integration Points

| Caller | Before | After |
|---|---|---|
| `modules/orchestrator/service.py::_build_agent` (line ~105) | `get_prompt("main_agent")` | `self._prompts.get_text_prompt(PromptId.MAIN_AGENT)` |
| `modules/payments/agent.py::build_payment_agent` | `get_prompt("payment_agent")` | new param `system_prompt: str` |
| `modules/payments/runner.py::_pay_invoice` (line ~100) | `build_payment_agent(llm, checkpointer, invoice)` | also passes `dependencies.prompts.get_text_prompt(PromptId.PAYMENT_AGENT)` |
| `modules/payments/runner.py::PaymentRunDependencies` | 5 fields | + `prompts: "PromptsClient"` |
| `modules/invoice_ingestor/service.py::_extract_invoice` (line ~52) | `INVOICE_EXTRACTION_PROMPT` | `self._prompts.get_text_prompt(PromptId.INVOICE_EXTRACTION)`; constructor gains `prompts` |
| `container.py::build_clients` | `LlmGatewayService(settings.llm)` | unchanged signature; also builds `prompts = PromptsClient(PromptsService(PROMPTS))` first and injects it into invoice_ingestor, payments deps and orchestrator; orchestrator also gets `tools` |
| `container.py::Clients` | — | + `prompts: PromptsClient` |
| `api/routers/__init__.py` | — | `api_router.include_router(diagnostics.diagnostics_router)` (no auth) |
| `api/app.py` | — | no change: `MissingStructuredResponseError` subclasses `AgentProviderError`, so the existing 503 handler covers it |

## Data Structures

```python
# contracts/prompts.py
class PromptId(StrEnum):
    MAIN_AGENT = "main_agent"
    PAYMENT_AGENT = "payment_agent"
    INVOICE_EXTRACTION = "invoice_extraction"
    EMAIL_TRIAGE = "email_triage"
    HELLO_WORLD = "hello_world"

class EmailMessage(StrictModel):
    sender: str
    subject: str
    body: str
    received_at: datetime | None = None

class EmailCategory(StrEnum):
    ACTION_REQUIRED = "action_required"
    INFORMATIONAL = "informational"
    MEETING = "meeting"
    NEWSLETTER = "newsletter"
    SPAM = "spam"
    PERSONAL = "personal"
    OTHER = "other"

class EmailPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class EmailTriage(StrictModel):
    """Final step: call this exactly once with the triage of the email."""
    category: EmailCategory
    priority: EmailPriority
    summary: str = Field(description="One or two sentences.")
    action_items: list[str] = []
    requires_reply: bool

class HelloWorldReport(StrictModel):
    """Final step: call this exactly once after calling both diagnostic tools."""
    greeting: str
    token: str = Field(description="The exact token returned by get_random_token.")
    token_generated_at: str = Field(description="The exact generated_at returned by get_random_token.")
    system_name: str = Field(description="The name field returned by get_system_profile.")
    tools_called: list[str]
```

Under `StrictModel`, `strict=True`, `ToolStrategy` parses the model's tool-call JSON. Enum and str fields validate from JSON strings in strict mode, but `datetime` would not. That is why `token_generated_at` is a `str`. `InvoiceData` already works under this setup.

```python
# contracts/tools.py
class RandomToken(StrictModel):
    token: str
    generated_at: str

class SystemProfile(StrictModel):
    name: str
    environment: str
    version: str
    capabilities: list[str]
```

```python
# core/config.py: LlmSettings (env prefix BLINKA_LLM__)
base_url: str = "https://openrouter.ai/api"
api_key: SecretStr = Field(validation_alias="OPENROUTER_API_KEY", default=SecretStr(""))
model: str = "anthropic/claude-haiku-5.5"
main_model: str | None = None
payments_model: str | None = None
max_tokens: int = 8192
timeout_s: float = 120
max_retries: int = 2
```
