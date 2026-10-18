import asyncio
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.bills import BillDocument
from contracts.payments import RunStatus
from contracts.prompts import PromptId
from core.logging_config import get_logger
from modules.payments.agent import build_payments_agent, stream_agent
from modules.payments.agent_state import RunState
from modules.payments.agent_tools import PaymentStepTools
from modules.payments.dependencies import PaymentRunDependencies
from modules.payments.errors import AgentIncompleteError
from modules.payments.events import (
    CANCELLED_STEP,
    COMPLETED_STEP,
    DECISION_FAILED_STEP,
    FAILED_STEP,
    STARTED_STEP,
    RunEventRecorder,
)
from modules.payments.settlement import fail_closed

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
    agent = build_payments_agent(
        model=dependencies.llm_gateway.model(PAYMENTS_MODEL_KIND),
        tools=PaymentStepTools(state, dependencies, events).as_tools(),
        system_prompt=dependencies.prompts.get_text_prompt(PromptId.PAYMENTS_AGENT),
        checkpointer=dependencies.checkpointer,
    )
    try:
        await stream_agent(agent, state, events, dependencies.thinking_flush_seconds)
    except asyncio.CancelledError:
        raise
    except Exception as agent_error:
        logger.exception("payments_agent_failed", run_id=state.run_id)
        state.agent_error = str(agent_error)


async def _finalize(
    state: RunState, dependencies: PaymentRunDependencies, events: RunEventRecorder
) -> None:
    is_settled = state.decision is not None or state.terminal_reason is not None
    if is_settled:
        return
    is_unsettled_duplicate = state.claim is not None and state.claim.duplicate_of is not None
    if state.claim is None or is_unsettled_duplicate:
        raise AgentIncompleteError(state.agent_error or AGENT_INCOMPLETE_REASON)
    await events.step(DECISION_FAILED_STEP)
    await fail_closed(dependencies, state.run_id, state.claim.bill, state.policy)
