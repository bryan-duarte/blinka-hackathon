from dataclasses import dataclass

from clients.auth import AuthClient
from clients.files import FilesClient
from clients.guardrails import GuardrailsClient
from clients.invoice_ingestor import InvoiceIngestorClient
from clients.llm import LlmGatewayClient
from clients.mcp import McpGatewayClient
from clients.orchestrator import OrchestratorClient
from clients.payments import PaymentsClient
from clients.prompts import PromptsClient
from clients.sessions import SessionsClient
from clients.tools import ToolsClient
from core.config import Settings
from core.db import Checkpointers, Pools
from modules.auth import AuthService, UsersRepository
from modules.files import FilesRepository, FilesService, ObjectStorageBackend
from modules.guardrails import GuardrailsService
from modules.invoice_ingestor import InvoiceIngestorService, InvoicesRepository
from modules.llm_gateway import LlmGatewayService
from modules.mcp_gateway import McpGatewayService
from modules.orchestrator import OrchestratorService
from modules.payments import ExecutionRegistry, PaymentsService, RunsRepository
from modules.payments.runner import PaymentRunDependencies
from modules.prompts import PROMPTS, PromptsService
from modules.sessions import (
    SessionsImmutableRepository,
    SessionsMutableRepository,
    SessionsService,
)
from modules.tools import ToolsService


@dataclass(frozen=True)
class Clients:
    auth: AuthClient
    files: FilesClient
    invoice_ingestor: InvoiceIngestorClient
    guardrails: GuardrailsClient
    llm: LlmGatewayClient
    mcp: McpGatewayClient
    prompts: PromptsClient
    tools: ToolsClient
    sessions: SessionsClient
    orchestrator: OrchestratorClient
    payments: PaymentsClient


async def build_clients(settings: Settings, pools: Pools, checkpointers: Checkpointers) -> Clients:
    llm = LlmGatewayClient(LlmGatewayService(settings.llm))
    prompts = PromptsClient(PromptsService(PROMPTS))
    guardrails = GuardrailsClient(GuardrailsService(settings.guardrails_enforce))
    mcp = McpGatewayClient(McpGatewayService())
    tools = ToolsClient(ToolsService())

    product_sessionmaker = pools.product.sessionmaker
    payments_sessionmaker = pools.payments.sessionmaker

    auth_service = AuthService(UsersRepository(product_sessionmaker), settings.jwt)
    auth = AuthClient(auth_service)

    storage = ObjectStorageBackend(
        endpoint_url=settings.storage.endpoint_url,
        bucket=settings.storage.bucket,
        access_key_id=settings.storage.access_key_id,
        secret_access_key=settings.storage.secret_access_key.get_secret_value(),
    )
    files_service = FilesService(FilesRepository(product_sessionmaker), storage)
    files = FilesClient(files_service)

    invoices_repository = InvoicesRepository(product_sessionmaker)
    invoice_ingestor_service = InvoiceIngestorService(files, llm, prompts, invoices_repository)
    invoice_ingestor = InvoiceIngestorClient(invoice_ingestor_service)

    sessions_service = SessionsService(
        SessionsMutableRepository(product_sessionmaker),
        SessionsImmutableRepository(payments_sessionmaker),
    )
    sessions = SessionsClient(sessions_service)

    runs_repository = RunsRepository(product_sessionmaker)
    registry = ExecutionRegistry()
    run_dependencies = PaymentRunDependencies(
        repository=runs_repository,
        llm_gateway=llm,
        payments_checkpointer=checkpointers.payments,
        invoice_ingestor=invoice_ingestor,
        sessions=sessions,
        prompts=prompts,
    )
    payments_service = PaymentsService(runs_repository, registry, run_dependencies, files)
    payments = PaymentsClient(payments_service)

    orchestrator_service = OrchestratorService(
        llm=llm,
        sessions=sessions,
        files=files,
        payments=payments,
        prompts=prompts,
        tools=tools,
        agent_checkpointer=checkpointers.agent,
    )
    orchestrator = OrchestratorClient(orchestrator_service)

    return Clients(
        auth=auth,
        files=files,
        invoice_ingestor=invoice_ingestor,
        guardrails=guardrails,
        llm=llm,
        mcp=mcp,
        prompts=prompts,
        tools=tools,
        sessions=sessions,
        orchestrator=orchestrator,
        payments=payments,
    )
