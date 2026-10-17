from dataclasses import dataclass
from typing import TYPE_CHECKING

from modules.payments.ledger_repository import LedgerRepository
from modules.payments.repository import RunsRepository

if TYPE_CHECKING:
    from clients.bills import BillsClient
    from clients.invoice_ingestor import InvoiceIngestorClient
    from clients.llm import LlmGatewayClient
    from clients.payment_policy import PaymentPolicyClient
    from clients.prompts import PromptsClient
    from clients.sessions import SessionsClient


@dataclass(frozen=True)
class PaymentRunDependencies:
    repository: RunsRepository
    ledger: LedgerRepository
    bills: "BillsClient"
    policy: "PaymentPolicyClient"
    invoice_ingestor: "InvoiceIngestorClient"
    llm_gateway: "LlmGatewayClient"
    prompts: "PromptsClient"
    sessions: "SessionsClient"
