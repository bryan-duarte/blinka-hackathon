from dataclasses import dataclass

from clients.auth import AuthClient
from clients.bills import BillsClient
from clients.files import FilesClient
from clients.guardrails import GuardrailsClient
from clients.inbox import InboxClient
from clients.invoice_ingestor import InvoiceIngestorClient
from clients.llm import LlmGatewayClient
from clients.mail_gateway import MailGatewayClient
from clients.mcp import McpGatewayClient
from clients.orchestrator import OrchestratorClient
from clients.payment_policy import PaymentPolicyClient
from clients.payments import PaymentsClient
from clients.prompts import PromptsClient
from clients.sessions import SessionsClient
from clients.tools import ToolsClient
from core.background import ExecutionRegistry
from core.config import Settings
from core.db import Checkpointers, Pools
from modules.auth import AuthService, UsersRepository
from modules.bills import BillsRepository, BillsService
from modules.files import FilesRepository, FilesService, ObjectStorageBackend
from modules.guardrails import BedrockGuardrailBackend, GuardrailsService
from modules.inbox import InboxDependencies, InboxRepository, InboxService
from modules.invoice_ingestor import InvoiceIngestorService
from modules.llm_gateway import LlmGatewayService
from modules.mail_gateway import MailGatewayService
from modules.mcp_gateway import McpGatewayService
from modules.orchestrator import OrchestratorService
from modules.payment_policy import PaymentPolicyRepository, PaymentPolicyService
from modules.payments import (
    LedgerRepository,
    PaymentRunDependencies,
    PaymentsService,
    RunsRepository,
)
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
    mail_gateway: MailGatewayClient
    inbox: InboxClient
    payment_policy: PaymentPolicyClient
    bills: BillsClient


async def build_clients(settings: Settings, pools: Pools, checkpointers: Checkpointers) -> Clients:
    llm = LlmGatewayClient(LlmGatewayService(settings.llm))
    prompts = PromptsClient(PromptsService(PROMPTS))
    guardrails_settings = settings.guardrails
    guardrail_backend = BedrockGuardrailBackend(
        guardrails_settings.guardrail_id,
        guardrails_settings.guardrail_version,
        guardrails_settings.aws_profile,
        guardrails_settings.aws_region,
    )
    guardrails = GuardrailsClient(GuardrailsService(guardrails_settings, guardrail_backend))
    mail_gateway = MailGatewayClient(MailGatewayService(settings.composio))
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

    payment_policy = PaymentPolicyClient(
        PaymentPolicyService(PaymentPolicyRepository(product_sessionmaker))
    )
    bills = BillsClient(BillsService(BillsRepository(product_sessionmaker)))

    invoice_ingestor = InvoiceIngestorClient(InvoiceIngestorService(files, llm, prompts))

    sessions_service = SessionsService(
        SessionsMutableRepository(product_sessionmaker),
        SessionsImmutableRepository(payments_sessionmaker),
    )
    sessions = SessionsClient(sessions_service)

    runs_repository = RunsRepository(product_sessionmaker)
    registry = ExecutionRegistry()
    run_dependencies = PaymentRunDependencies(
        repository=runs_repository,
        ledger=LedgerRepository(product_sessionmaker),
        bills=bills,
        policy=payment_policy,
        invoice_ingestor=invoice_ingestor,
        llm_gateway=llm,
        prompts=prompts,
        sessions=sessions,
    )
    payments_service = PaymentsService(runs_repository, registry, run_dependencies, files)
    payments = PaymentsClient(payments_service)

    inbox_repository = InboxRepository(product_sessionmaker)
    inbox_dependencies = InboxDependencies(
        repository=inbox_repository,
        files=files,
        guardrails=guardrails,
        payments=payments,
        mail_gateway=mail_gateway,
        bills=bills,
    )
    inbox_service = InboxService(
        inbox_repository,
        ExecutionRegistry(),
        inbox_dependencies,
        auth=auth,
        callback_url=settings.composio.callback_url,
    )
    inbox = InboxClient(inbox_service)

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
        mail_gateway=mail_gateway,
        inbox=inbox,
        payment_policy=payment_policy,
        bills=bills,
    )
