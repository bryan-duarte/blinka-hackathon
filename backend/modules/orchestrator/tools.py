import json
from typing import TYPE_CHECKING
from uuid import UUID

from langchain_core.tools import BaseTool, tool

from contracts.auth import CurrentUser
from contracts.payments import PaymentRunTrigger

if TYPE_CHECKING:
    from clients.payments import PaymentsClient

INITIATE_PAYMENTS_TOOL_NAME = "initiate_payments"


def build_initiate_payments_tool(
    payments: "PaymentsClient", owner: CurrentUser, session_id: UUID
) -> BaseTool:
    @tool(INITIATE_PAYMENTS_TOOL_NAME)
    async def initiate_payments(file_id: UUID, reason: str = "") -> dict:
        """Start a background invoice payment run for the given invoice file.

        Returns the run id immediately; the payment executes in the background.
        Always report the returned run id to the user.
        """
        trigger = PaymentRunTrigger(file_id=file_id, session_id=session_id)
        accepted = await payments.start_run(trigger, owner)
        return {"run_id": str(accepted.run_id), "status": str(accepted.status)}

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
