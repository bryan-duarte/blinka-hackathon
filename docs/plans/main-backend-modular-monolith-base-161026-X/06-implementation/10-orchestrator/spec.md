# Orchestrator (Main Agent)

## Overview

Main conversational DeepAgent (`deepagents.create_deep_agent`) with PG-2 checkpointer. Owns the `initiate_payments` tool (inline until `tools/` graduates from skeleton) and both chat endpoints (JSON + SSE).

## Files to Create

- `backend/modules/orchestrator/__init__.py` — facade: `OrchestratorService`, `OrchestratorError`
- `backend/modules/orchestrator/errors.py` — `OrchestratorError`; `GuardrailRejectionError` is shared — define it in `modules/guardrails` and import here.
- `backend/modules/orchestrator/service.py`:

```python
class OrchestratorService:
    def __init__(self, llm: LlmGatewayClient, sessions: SessionsClient,
                 files: FilesClient, payments: PaymentsClient,
                 agent_checkpointer,          # opened AsyncPostgresSaver (PG-2)
                 payments_session_hint=None) -> None: ...

    def _build_agent(self):
        # create_deep_agent(model=llm.model("main"),
        #                   system_prompt=get_prompt("main_agent"),
        #                   tools=[initiate_payments],
        #                   checkpointer=self._checkpointer)   # verify kwarg vs .compile() for pinned deepagents
```

- `backend/modules/orchestrator/tools.py` — `initiate_payments` tool:

```python
@tool
async def initiate_payments(file_id: UUID, reason: str = "") -> dict:
    """Start a background invoice payment run. Returns the run id immediately."""
    accepted = await payments.start_run(PaymentRunTrigger(file_id=file_id, session_id=session_id))
    return {"run_id": str(accepted.run_id), "status": accepted.status}
```

The tool closes over `payments` client + current `session_id` (built per-request in a small factory — tools are request-scoped, the agent is process-scoped).

- Flow methods:

```python
async def chat(self, user: CurrentUser, request: ChatRequest) -> ChatResponse
# guardrails handled by ROUTE (see below); here:
# 1. session_id = await sessions.ensure_session(user, request.session_id)
# 2. file_context = await files.get_context(user, request.file_ids) if request.file_ids else ""
# 3. result = await agent.ainvoke({"messages": [...]}, config={"configurable": {"thread_id": str(session_id)}})
# 4. reply = last AIMessage.content ; detect payments_scheduled via tool return in messages
# 5. return ChatResponse(reply, session_id, payments_run_id)

async def stream_chat(self, user, request) -> AsyncIterator[ChatStreamEvent]
# same setup, then `agent.astream_events(input, config, version="v2")`:
#   on_chat_model_stream -> ChatStreamEvent(type="token", data={"text": delta})
#   on_tool_start (initiate_payments) -> type="tool_started"
#   custom yield after tool result -> type="payments_scheduled" data={"run_id"}
#   end -> type="done" data={"session_id": ...}
# finally: generator is wrapped by the route into SSE frames
```

- `backend/api/routers/chat.py` — `chat_router = APIRouter(tags=["chat"])`:
  - `POST /chat` → 200 `ChatResponse`
  - `POST /chat/stream` → `StreamingResponse(media_type="text/event-stream")`; frames `event: message\ndata: {model_dump_json()}\n\n`
  - BOTH routes: `verdict = await guardrails.check(GuardrailCheckRequest(context=request.message + file_context))` first; `not verdict.allowed` → raise `GuardrailRejectionError(violations)` (→ 422 handler in `app.py`).
- `backend/clients/orchestrator.py` — `OrchestratorClient.chat`, `OrchestratorClient.stream_chat`.

## Implementation Guidelines

- `thread_id = str(session_id)` — session id IS the checkpoint thread id; conversation resumes across process restarts via PG-2.
- Streaming must `yield` frequently and never buffer the whole reply; on client disconnect, let `astream_events` cancellation propagate (checkpoint keeps state).
- File context is prepended as a system-ish preamble message, never concatenated into the user's raw message string.

## Dependencies

08-llm-gateway-prompts, 09-sessions, 06-files-storage, 11-payments (client), 12-stub-modules (guardrails client).

## Integration Notes

Emits: `PaymentRunTrigger` (with `session_id`) → payments. Consumes: `ChatRequest`/`ChatStreamEvent` contracts. The agent kwarg question (checkpointer in `create_deep_agent` vs `.compile`) must be verified against the pinned `deepagents` version — same pattern as `payments/agent.py`; solve once, mirror both.
