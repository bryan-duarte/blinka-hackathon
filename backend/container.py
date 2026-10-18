from dataclasses import dataclass

from clients.auth import AuthClient
from clients.bills import BillsClient
from clients.document_vision import DocumentVisionClient
from clients.files import FilesClient
from clients.guardrails import GuardrailsClient
from clients.inbox import InboxClient
from clients.invoice_ingestor import InvoiceIngestorClient
from clients.llm import LlmGatewayClient
from clients.mail_gateway import MailGatewayClient
from clients.mcp import McpGatewayClient
from clients.payment_policy import PaymentPolicyClient
from clients.payments import PaymentsClient
from clients.prompts import PromptsClient
from clients.realtime import RealtimeClient
from clients.whatsapp_gateway import WhatsAppGatewayClient
from core.background import ExecutionRegistry
from core.config import Settings
from core.db import Checkpointers, Pools
from modules.auth import AuthService, UsersRepository
from modules.bills import BillsRepository, BillsService
from modules.document_vision import TextractExpenseReader
from modules.files import (
    FilesRepository,
    FilesService,
    MalwareScanService,
    ObjectStorageBackend,
)
from modules.guardrails import BedrockGuardrailBackend, GuardrailsService
from modules.inbox import InboxDependencies, InboxNotifier, InboxRepository, InboxService
from modules.invoice_ingestor import InvoiceIngestorService
from modules.llm_gateway import LlmGatewayService
from modules.mail_gateway import MailGatewayService
from modules.mcp_gateway import McpGatewayService
from modules.payment_policy import PaymentPolicyRepository, PaymentPolicyService
from modules.payments import (
    LedgerRepository,
    PaymentRunDependencies,
    PaymentsService,
    RunsRepository,
)
from modules.prompts import PROMPTS, PromptsService
from modules.realtime import (
    AppSyncEventsBackend,
    NullRealtimeBackend,
    RealtimeBackend,
    RealtimeService,
)
from modules.whatsapp_gateway import WhatsAppGatewayService

MILLISECONDS_PER_SECOND = 1000


@dataclass(frozen=True)
class Clients:
    auth: AuthClient
    files: FilesClient
    invoice_ingestor: InvoiceIngestorClient
    guardrails: GuardrailsClient
    llm: LlmGatewayClient
    mcp: McpGatewayClient
    prompts: PromptsClient
    realtime: RealtimeClient
    payments: PaymentsClient
    mail_gateway: MailGatewayClient
    whatsapp_gateway: WhatsAppGatewayClient
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
    whatsapp_gateway = WhatsAppGatewayClient(WhatsAppGatewayService(settings.kapso))
    mcp = McpGatewayClient(McpGatewayService())
    realtime = RealtimeClient(
        RealtimeService(_realtime_backend(settings), settings.realtime.namespace)
    )

    product_sessionmaker = pools.product.sessionmaker

    auth_service = AuthService(UsersRepository(product_sessionmaker), settings.jwt)
    auth = AuthClient(auth_service)

    storage_settings = settings.storage
    storage = ObjectStorageBackend(
        storage_settings.bucket, storage_settings.aws_profile, storage_settings.region
    )
    files_service = FilesService(
        FilesRepository(product_sessionmaker),
        storage,
        MalwareScanService(storage, storage_settings),
    )
    files = FilesClient(files_service)

    payment_policy = PaymentPolicyClient(
        PaymentPolicyService(PaymentPolicyRepository(product_sessionmaker))
    )
    bills = BillsClient(BillsService(BillsRepository(product_sessionmaker)))

    document_vision = DocumentVisionClient(
        TextractExpenseReader(settings.textract.aws_profile, settings.textract.region)
    )
    invoice_ingestor = InvoiceIngestorClient(
        InvoiceIngestorService(files, llm, prompts, document_vision)
    )

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
        checkpointer=checkpointers.payments,
        realtime=realtime,
        thinking_flush_seconds=settings.realtime.thinking_flush_ms / MILLISECONDS_PER_SECOND,
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
        whatsapp_gateway=whatsapp_gateway,
        bills=bills,
        notifier=InboxNotifier(realtime),
    )
    inbox_service = InboxService(
        inbox_repository,
        ExecutionRegistry(),
        inbox_dependencies,
        auth=auth,
        callback_url=settings.composio.callback_url,
        kapso=settings.kapso,
    )
    inbox = InboxClient(inbox_service)

    return Clients(
        auth=auth,
        files=files,
        invoice_ingestor=invoice_ingestor,
        guardrails=guardrails,
        llm=llm,
        mcp=mcp,
        prompts=prompts,
        realtime=realtime,
        payments=payments,
        mail_gateway=mail_gateway,
        whatsapp_gateway=whatsapp_gateway,
        inbox=inbox,
        payment_policy=payment_policy,
        bills=bills,
    )


def _realtime_backend(settings: Settings) -> RealtimeBackend:
    realtime_settings = settings.realtime
    is_realtime_configured = realtime_settings.enabled and bool(realtime_settings.http_domain)
    if not is_realtime_configured:
        return NullRealtimeBackend()
    return AppSyncEventsBackend(realtime_settings)
