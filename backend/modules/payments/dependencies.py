from dataclasses import dataclass
from typing import TYPE_CHECKING

from modules.payments.ledger_repository import LedgerRepository
from modules.payments.repository import RunsRepository

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver

    from clients.bills import BillsClient
    from clients.fx import FxClient
    from clients.invoice_ingestor import InvoiceIngestorClient
    from clients.llm import LlmGatewayClient
    from clients.payment_policy import PaymentPolicyClient
    from clients.prompts import PromptsClient
    from clients.realtime import RealtimeClient


@dataclass(frozen=True)
class PaymentRunDependencies:
    repository: RunsRepository
    ledger: LedgerRepository
    bills: "BillsClient"
    fx: "FxClient"
    policy: "PaymentPolicyClient"
    invoice_ingestor: "InvoiceIngestorClient"
    llm_gateway: "LlmGatewayClient"
    prompts: "PromptsClient"
    checkpointer: "BaseCheckpointSaver | None"
    realtime: "RealtimeClient"
    thinking_flush_seconds: float
