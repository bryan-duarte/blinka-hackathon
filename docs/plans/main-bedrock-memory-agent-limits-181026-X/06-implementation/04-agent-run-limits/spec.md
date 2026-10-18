# Agent Run Limits

## Overview

Bound every payments-agent run with three limits: 180 s wall clock, 30 tool calls and 35 agent model calls. Hitting any of them escalates the bill to a human (REVIEW), records a `limit_exceeded` run step, and shows a dedicated timeline node.

## Files to Modify/Create

- `backend/core/config.py`: new `AgentSettings` (`BLINKA_AGENT__`), added to `Settings` as `agent: AgentSettings = Field(default_factory=AgentSettings)`.
- `backend/modules/payments/limits.py` (new): `AgentLimit` (StrEnum), `AgentRunLimits`, `AgentLimitHit`, `limit_explanation(hit) -> str`, and `LIMIT_EXCEEDED_REASON_PREFIX = "limit_exceeded:"`.
- `backend/modules/payments/errors.py`: no new error class is needed. The middleware and timeout errors are mapped straight to `AgentLimitHit` in the runner, which keeps the surface minimal.
- `backend/modules/payments/agent_state.py`: `RunState.limit_exceeded: AgentLimitHit | None = None`.
- `backend/modules/payments/dependencies.py`: `PaymentRunDependencies.limits: AgentRunLimits`.
- `backend/container.py:140-152`: `limits=AgentRunLimits(settings.agent.run_timeout_s, settings.agent.max_tool_calls, settings.agent.max_model_calls)`.
- `backend/modules/payments/agent.py`: `build_payments_agent(model, tools, system_prompt, checkpointer, limits)` adds the two middlewares.
- `backend/modules/payments/runner.py`: `_run_agent` (timeout and error mapping, emits the step) and `_finalize` (escalation path).
- `backend/modules/payments/events.py`: `LIMIT_EXCEEDED_STEP = "limit_exceeded"`.
- `backend/modules/payments/phrases.py` `STEP_PHRASES`: `"limit_exceeded": ("The agent hit its safety limit; a person will review.", "Stopped the agent at its safety limit.")`, matching the tuple style of the neighbouring entries.
- `backend/.env.example`: commented `BLINKA_AGENT__RUN_TIMEOUT_S=180`, `BLINKA_AGENT__MAX_TOOL_CALLS=30`, `BLINKA_AGENT__MAX_MODEL_CALLS=35`.
- `frontend/src/lib/types.ts`: `LimitExceededPayload`.
- `frontend/src/lib/runEvents.ts`: `LIMIT_EXCEEDED_STEP` constant and `latestLimitExceeded(activity): LimitExceededPayload | null`.
- `frontend/src/components/runs/RunTimeline.tsx` `buildNodes` (`:135-190`): push a limit node before the decided/stopped node.

## Implementation Guidelines

```python
# orientative — payments/agent.py
from langchain.agents.middleware import ModelCallLimitMiddleware, TodoListMiddleware, ToolCallLimitMiddleware

LIMIT_EXIT_BEHAVIOR = "error"

def build_payments_agent(model, tools, system_prompt, checkpointer, limits: AgentRunLimits) -> CompiledStateGraph:
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=[
            TodoListMiddleware(),
            ToolCallLimitMiddleware(run_limit=limits.max_tool_calls, exit_behavior=LIMIT_EXIT_BEHAVIOR),
            ModelCallLimitMiddleware(run_limit=limits.max_model_calls, exit_behavior=LIMIT_EXIT_BEHAVIOR),
        ],
        checkpointer=checkpointer,
        name=PAYMENTS_AGENT_GRAPH_NAME,
    )
```
- `run_limit` counts within one `astream_events` invocation. Each run uses its own `thread_id=run_id`, so run and thread are equivalent here.
- `ToolCallLimitMiddleware` with no `tool_name` counts every tool, including `write_todos`. A clean run is about 13.
- The model-call limit counts only the agent's `model` node. The nested checker and extraction LLM calls inside tools don't count. Those have their own per-call `timeout_s`.
- Keep `AGENT_RECURSION_LIMIT = 80` as a backstop. Map `GraphRecursionError` to a limit hit too (`AgentLimit.TOOL_CALLS` with threshold `AGENT_RECURSION_LIMIT`), so a recursion stop is also explained, not left as a generic error.

```python
# orientative — payments/runner.py
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError
from langgraph.errors import GraphRecursionError

async def _run_agent(state, dependencies, events) -> None:
    limits = dependencies.limits
    agent = build_payments_agent(..., limits=limits)
    try:
        async with asyncio.timeout(limits.run_timeout_s):
            await stream_agent(agent, state, events, dependencies.thinking_flush_seconds)
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        await _record_limit(state, events, AgentLimitHit(AgentLimit.TIME, limits.run_timeout_s))
    except ToolCallLimitExceededError:
        await _record_limit(state, events, AgentLimitHit(AgentLimit.TOOL_CALLS, limits.max_tool_calls))
    except ModelCallLimitExceededError:
        await _record_limit(state, events, AgentLimitHit(AgentLimit.MODEL_CALLS, limits.max_model_calls))
    except GraphRecursionError:
        await _record_limit(state, events, AgentLimitHit(AgentLimit.TOOL_CALLS, AGENT_RECURSION_LIMIT))
    except Exception as agent_error:
        logger.exception("payments_agent_failed", run_id=state.run_id)
        state.agent_error = str(agent_error)

async def _record_limit(state, events, hit: AgentLimitHit) -> None:
    logger.warning("payments_agent_limit_exceeded", run_id=state.run_id, limit=hit.limit, threshold=hit.threshold)
    state.limit_exceeded = hit
    state.agent_error = f"{LIMIT_EXCEEDED_REASON_PREFIX}{hit.limit}"
    await events.step(LIMIT_EXCEEDED_STEP, {"limit": hit.limit, "threshold": hit.threshold})

async def _finalize(state, dependencies, events) -> None:
    is_settled = state.decision is not None or state.terminal_reason is not None
    if is_settled:
        return
    is_unsettled_duplicate = state.claim is not None and state.claim.duplicate_of is not None
    if state.claim is None or is_unsettled_duplicate:
        raise AgentIncompleteError(state.agent_error or AGENT_INCOMPLETE_REASON)
    await events.step(DECISION_FAILED_STEP)
    explanation = limit_explanation(state.limit_exceeded) if state.limit_exceeded else TECHNICAL_ERROR_EXPLANATION
    await fail_closed(dependencies, state.run_id, state.claim.bill, state.policy, explanation)
```
- `asyncio.timeout` turns the internal cancellation into `TimeoutError` at the `async with` exit. External shutdown cancellation still surfaces as `CancelledError` and is re-raised, the same as today.
- **A timeout during an in-flight `settle_decision`** is safe. `commit_settlement` is a single transaction. If it committed, `state.decision` is set and `_finalize` returns. If not, `fail_closed` either finds the reserved payment (`payment_for_bill`) or records the technical review.
- `limit_explanation`, orientative: `"The agent stopped at its safety limit ({label}: {threshold}). A person needs to review this invoice."` with labels `{"time": "time, seconds", "tool_calls": "tool calls", "model_calls": "model calls"}`.
- Import `TECHNICAL_ERROR_EXPLANATION` from `settlement.py`, or let `fail_closed` keep its default by passing the explanation only when there's a limit hit.

```tsx
// orientative — RunTimeline.tsx buildNodes, before the `if (decision)` block
const limitHit = latestLimitExceeded(activity);
if (limitHit) {
  nodes.push({
    key: "limit",
    title: "Stopped at a safety limit",
    detail: LIMIT_DETAILS[limitHit.limit](limitHit.threshold),
    isError: true,
  });
}
```
- `LIMIT_DETAILS` example: `time` → `` `Ran longer than ${t} seconds` ``, `tool_calls` → `` `Used more than ${t} tool calls` ``, `model_calls` → `` `Made more than ${t} model calls` ``.
- Do **not** add `limit_exceeded` to `TERMINAL_RUN_STEPS`. A `decided`/`decision_failed`/`failed` step always follows.
- UI copy follows `frontend/DESIGN.md` (no em-dashes in UI copy).

## Dependencies

- Module 02 (the agent runs on Bedrock). The middleware ships in langchain 1.4.6, which is already installed.

## Integration Notes

- `tests/test_payments_agent.py` calls `build_payments_agent(...)`. Update the call sites to pass an `AgentRunLimits`, so existing tests compile. The existing `limit // 4` recursion test now expects the limit mapping when it goes through the runner. Only adjust if it exercises `_run_agent`.
- Accountability shows FAILED runs with `row.error` (`limit_exceeded:<limit>`). Escalated bills show the `limit_explanation` text in the decision explanation and the `ERR` rule.
