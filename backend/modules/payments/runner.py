import asyncio
from uuid import UUID

from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError
from langgraph.errors import GraphRecursionError

from contracts.auth import CurrentUser
from contracts.bills import BillDocument
from contracts.payments import RunStatus
from contracts.prompts import PromptId
from core.logging_config import get_logger
from modules.payments.agent import agent_recursion_limit, build_payments_agent, stream_agent
from modules.payments.agent_state import RunState
from modules.payments.agent_tools import PaymentStepTools
from modules.payments.dependencies import PaymentRunDependencies
from modules.payments.errors import AgentIncompleteError
from modules.payments.events import (
    CANCELLED_STEP,
    COMPLETED_STEP,
    DECISION_FAILED_STEP,
    FAILED_STEP,
    LIMIT_EXCEEDED_STEP,
    STARTED_STEP,
    RunEventRecorder,
)
from modules.payments.limits import (
    AgentLimit,
    AgentLimitHit,
    AgentRunLimits,
    limit_explanation,
    limit_failure_reason,
)
from modules.payments.settlement import TECHNICAL_ERROR_EXPLANATION, fail_closed

logger = get_logger(__name__)

PAYMENTS_AGENT_NAME = "payments"
PAYMENTS_MODEL_KIND = "payments"
SHUTDOWN_CANCELLATION_REASON = "cancelled on shutdown"
AGENT_INCOMPLETE_REASON = "agent_incomplete"


async def run_execution(
    run_id: UUID,
    owner: CurrentUser,
    bill_source_id: UUID,
    dependencies: PaymentRunDependencies,
) -> None:
    repository = dependencies.repository
    events = RunEventRecorder(repository, dependencies.realtime, owner.user_id, run_id)
    try:
        await events.step(STARTED_STEP)
        await repository.attach_run_to_evidence(bill_source_id, run_id)
        state = await _initial_state(run_id, owner, bill_source_id, dependencies)
        events.bind_item(state.source.inbox_email_id)
        await _run_agent(state, dependencies, events)
        await _finalize(state, dependencies, events)
        await events.step(COMPLETED_STEP)
        await repository.update_status(run_id, RunStatus.COMPLETED)
        logger.info("payment_run_completed", run_id=run_id)
    except asyncio.CancelledError:
        await events.step(CANCELLED_STEP)
        await repository.update_status(run_id, RunStatus.FAILED, error=SHUTDOWN_CANCELLATION_REASON)
        raise
    except AgentIncompleteError as incomplete_error:
        failure_reason = str(incomplete_error)
        logger.warning("payment_run_agent_incomplete", run_id=run_id, reason=failure_reason)
        await events.step(FAILED_STEP, {"error": failure_reason})
        await repository.update_status(run_id, RunStatus.FAILED, error=failure_reason)
    except Exception as execution_error:
        logger.exception("payment_run_failed", run_id=run_id)
        await events.step(FAILED_STEP, {"error": str(execution_error)})
        await repository.update_status(run_id, RunStatus.FAILED, error=str(execution_error))


async def _initial_state(
    run_id: UUID,
    owner: CurrentUser,
    bill_source_id: UUID,
    dependencies: PaymentRunDependencies,
) -> RunState:
    source = await dependencies.bills.get_source(owner.user_id, bill_source_id)
    document = BillDocument(
        body_text=source.body_text, file_id=source.file_id, sender=source.sender
    )
    return RunState(run_id=run_id, owner=owner, source=source, document=document)


async def _run_agent(
    state: RunState, dependencies: PaymentRunDependencies, events: RunEventRecorder
) -> None:
    limits = dependencies.limits
    agent = build_payments_agent(
        model=dependencies.llm_gateway.model(PAYMENTS_MODEL_KIND),
        tools=PaymentStepTools(state, dependencies, events).as_tools(),
        system_prompt=dependencies.prompts.get_text_prompt(PromptId.PAYMENTS_AGENT),
        checkpointer=dependencies.checkpointer,
        limits=limits,
    )
    run_deadline = asyncio.timeout(limits.run_timeout_s)
    try:
        async with run_deadline:
            await stream_agent(
                agent,
                state,
                events,
                dependencies.thinking_flush_seconds,
                agent_recursion_limit(limits),
            )
    except asyncio.CancelledError:
        raise
    except Exception as agent_error:
        limit_hit = _limit_hit(agent_error, run_deadline, limits)
        if limit_hit is None:
            logger.exception("payments_agent_failed", run_id=state.run_id)
            state.agent_error = str(agent_error)
            return
        if _is_settled(state):
            logger.warning(
                "payments_agent_limit_after_settle", run_id=state.run_id, limit=limit_hit.limit
            )
            return
        await _record_limit(state, events, limit_hit)


def _limit_hit(
    agent_error: Exception, run_deadline: asyncio.Timeout, limits: AgentRunLimits
) -> AgentLimitHit | None:
    is_run_timeout = isinstance(agent_error, TimeoutError) and run_deadline.expired()
    if is_run_timeout:
        return AgentLimitHit(AgentLimit.TIME, limits.run_timeout_s)
    if isinstance(agent_error, ToolCallLimitExceededError):
        return AgentLimitHit(AgentLimit.TOOL_CALLS, limits.max_tool_calls)
    if isinstance(agent_error, ModelCallLimitExceededError | GraphRecursionError):
        return AgentLimitHit(AgentLimit.MODEL_CALLS, limits.max_model_calls)
    return None


async def _record_limit(
    state: RunState, events: RunEventRecorder, limit_hit: AgentLimitHit
) -> None:
    logger.warning(
        "payments_agent_limit_exceeded",
        run_id=state.run_id,
        limit=limit_hit.limit,
        threshold=limit_hit.threshold,
    )
    state.limit_exceeded = limit_hit
    state.agent_error = limit_failure_reason(limit_hit)
    await events.step(
        LIMIT_EXCEEDED_STEP, {"limit": limit_hit.limit, "threshold": limit_hit.threshold}
    )


async def _finalize(
    state: RunState, dependencies: PaymentRunDependencies, events: RunEventRecorder
) -> None:
    if _is_settled(state):
        return
    is_unsettled_duplicate = state.claim is not None and state.claim.duplicate_of is not None
    if state.claim is None or is_unsettled_duplicate:
        raise AgentIncompleteError(state.agent_error or AGENT_INCOMPLETE_REASON)
    latest_decision = await dependencies.ledger.latest_decision(state.claim.bill.bill_id)
    is_settled_before_interruption = (
        latest_decision is not None and latest_decision.run_id == state.run_id
    )
    if is_settled_before_interruption:
        logger.warning("payment_run_settled_before_interruption", run_id=state.run_id)
        return
    await events.step(DECISION_FAILED_STEP)
    explanation = (
        limit_explanation(state.limit_exceeded)
        if state.limit_exceeded is not None
        else TECHNICAL_ERROR_EXPLANATION
    )
    await fail_closed(dependencies, state.run_id, state.claim.bill, state.policy, explanation)


def _is_settled(state: RunState) -> bool:
    return state.decision is not None or state.terminal_reason is not None
