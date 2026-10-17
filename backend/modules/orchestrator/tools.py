import json
from typing import TYPE_CHECKING
from uuid import UUID

from langchain_core.tools import BaseTool, tool

from contracts.auth import CurrentUser
from contracts.bills import BillSourceType

if TYPE_CHECKING:
    from clients.payments import PaymentsClient

INITIATE_PAYMENTS_TOOL_NAME = "initiate_payments"


def build_initiate_payments_tool(
    payments: "PaymentsClient", owner: CurrentUser, session_id: UUID
) -> BaseTool:
    @tool(INITIATE_PAYMENTS_TOOL_NAME)
    async def initiate_payments(file_id: UUID, reason: str = "") -> dict:
        """Send an uploaded bill to the payments agent, which decides to pay, hold or escalate it.

        Returns the run id immediately and whether this bill was already received.
        Always report the returned run id to the user.
        """
        accepted = await payments.start_file_run(
            owner,
            file_id,
            BillSourceType.CHAT,
            f"{session_id}:{file_id}",
            body_text=reason,
            session_id=session_id,
        )
        return accepted.model_dump(mode="json")

    return initiate_payments


def extract_run_id(tool_output: str) -> UUID | None:
    try:
        tool_payload = json.loads(tool_output)
    except (json.JSONDecodeError, TypeError):
        return None
    raw_run_id = tool_payload.get("run_id") if isinstance(tool_payload, dict) else None
    if raw_run_id is None:
        return None
    try:
        return UUID(raw_run_id)
    except ValueError:
        return None
