import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING
from uuid import UUID

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver

from contracts.auth import CurrentUser
from contracts.invoices import InvoiceData, InvoiceParseResult
from contracts.payments import RunStatus
from contracts.prompts import PromptId
from core.agents import last_reply_text, thread_config
from core.logging_config import get_logger
from modules.invoice_ingestor.errors import InvoiceParseError
from modules.payments.agent import PAYMENTS_AGENT_NAME, build_payment_agent
from modules.payments.repository import RunsRepository

if TYPE_CHECKING:
    from clients.invoice_ingestor import InvoiceIngestorClient
    from clients.llm import LlmGatewayClient
    from clients.prompts import PromptsClient
    from clients.sessions import SessionsClient

logger = get_logger(__name__)

SHUTDOWN_CANCELLATION_REASON = "cancelled on shutdown"
INVOICE_PARSE_FAILURE_REASON = "invoice parse failed"


class ExecutionRegistry:
    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    def spawn(self, run_id: UUID, execution: Coroutine[object, object, None]) -> None:
        task = asyncio.create_task(execution)
        self._tasks[run_id] = task
        task.add_done_callback(partial(self._reap, run_id))

    def _reap(self, run_id: UUID, task: asyncio.Task[None]) -> None:
        self._tasks.pop(run_id, None)
        if task.cancelled():
            return
        task_error = task.exception()
        if task_error is not None:
            logger.error("run_task_crashed", run_id=run_id, exc_info=task_error)

    async def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()


@dataclass(frozen=True)
class PaymentRunDependencies:
    repository: RunsRepository
    llm_gateway: "LlmGatewayClient"
    payments_checkpointer: BaseCheckpointSaver | None
    invoice_ingestor: "InvoiceIngestorClient"
    sessions: "SessionsClient"
    prompts: "PromptsClient"


async def run_execution(
    run_id: UUID,
    owner: CurrentUser,
    file_id: UUID,
    session_id: UUID | None,
    dependencies: PaymentRunDependencies,
) -> None:
    repository = dependencies.repository
    await repository.insert_event(run_id, "started", {})
    await repository.update_status(run_id, RunStatus.RUNNING)
    try:
        await _pay_invoice(run_id, owner, file_id, session_id, dependencies)
    except InvoiceParseError:
        await repository.insert_event(run_id, "invoice_parse_failed", {"file_id": str(file_id)})
        await repository.update_status(run_id, RunStatus.FAILED, error=INVOICE_PARSE_FAILURE_REASON)
    except asyncio.CancelledError:
        await repository.insert_event(run_id, "cancelled", {})
        await repository.update_status(run_id, RunStatus.FAILED, error=SHUTDOWN_CANCELLATION_REASON)
        raise
    except Exception as execution_error:
        logger.exception("payment_run_failed", run_id=run_id)
        await repository.insert_event(run_id, "failed", {"error": str(execution_error)})
        await repository.update_status(run_id, RunStatus.FAILED, error=str(execution_error))


async def _pay_invoice(
    run_id: UUID,
    owner: CurrentUser,
    file_id: UUID,
    session_id: UUID | None,
    dependencies: PaymentRunDependencies,
) -> None:
    repository = dependencies.repository
    parse_result = await dependencies.invoice_ingestor.parse(owner, file_id)
    invoice = _require_invoice(parse_result)
    await repository.insert_event(run_id, "invoice_parsed", invoice.model_dump(mode="json"))
    agent = build_payment_agent(
        dependencies.llm_gateway.model("payments"),
        dependencies.payments_checkpointer,
        invoice,
        dependencies.prompts.get_text_prompt(PromptId.PAYMENT_AGENT),
    )
    agent_state = await agent.ainvoke(
        {"messages": [HumanMessage(content=_seed_message(invoice))]},
        config=thread_config(run_id),
    )
    reply_summary = last_reply_text(agent_state)
    await repository.insert_event(run_id, "completed", {"summary": reply_summary})
    await repository.update_status(run_id, RunStatus.COMPLETED)
    await _record_execution(dependencies, owner, session_id, invoice, reply_summary)
    logger.info("payment_run_completed", run_id=run_id)


def _require_invoice(parse_result: InvoiceParseResult) -> InvoiceData:
    if parse_result.invoice is None:
        raise InvoiceParseError
    return parse_result.invoice


def _seed_message(invoice: InvoiceData) -> str:
    return "Pay the following invoice end to end. Invoice data:\n" + invoice.model_dump_json()


async def _record_execution(
    dependencies: PaymentRunDependencies,
    owner: CurrentUser,
    session_id: UUID | None,
    invoice: InvoiceData,
    reply_summary: str,
) -> None:
    if session_id is None:
        return
    await dependencies.sessions.record_execution(
        owner,
        session_id,
        PAYMENTS_AGENT_NAME,
        f"invoice {invoice.number} from {invoice.vendor}",
        reply_summary,
    )
