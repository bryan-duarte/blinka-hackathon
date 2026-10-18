from dataclasses import dataclass

from clients.accountability import AccountabilityClient
from clients.auth import AuthClient
from clients.bills import BillsClient
from clients.demo import DemoClient
from clients.document_vision import DocumentVisionClient
from clients.files import FilesClient
from clients.fx import FxClient
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
from contracts.demo import KitDestinations
from core.background import ExecutionRegistry
from core.config import Settings
from core.db import Checkpointers, Pools
from core.work_queue import QueueLimits
from modules.accountability import AccountabilityRepository, AccountabilityService
from modules.auth import AuthService, UsersRepository
from modules.bills import BillsRepository, BillsService
from modules.demo import DemoResetRepository, DemoSeeder, DemoSeedRepository, DemoService
from modules.document_vision import TextractExpenseReader
from modules.files import (
    FilesRepository,
    FilesService,
    MalwareScanService,
    ObjectStorageBackend,
)
from modules.fx import FxRepository, FxService, OpenErApiProvider
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
    fx: FxClient
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
    demo: DemoClient
    accountability: AccountabilityClient


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

    demo_settings = settings.demo
    auth_service = AuthService(
        UsersRepository(product_sessionmaker),
        settings.jwt,
        allowed_email=demo_settings.email if demo_settings.enabled else None,
    )
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
    fx = FxClient(
        FxService(FxRepository(product_sessionmaker), OpenErApiProvider(settings.fx), settings.fx)
    )

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
        fx=fx,
        policy=payment_policy,
        invoice_ingestor=invoice_ingestor,
        llm_gateway=llm,
        prompts=prompts,
        checkpointer=checkpointers.agent,
        realtime=realtime,
        thinking_flush_seconds=settings.realtime.thinking_flush_ms / MILLISECONDS_PER_SECOND,
    )
    workers = settings.workers
    payments_service = PaymentsService(
        runs_repository,
        registry,
        run_dependencies,
        files,
        auth=auth,
        queue_limits=QueueLimits(workers.agent_run_concurrency, workers.poll_interval_seconds),
    )
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
        notifier=InboxNotifier(realtime, inbox_repository),
    )
    inbox_service = InboxService(
        inbox_repository,
        ExecutionRegistry(),
        inbox_dependencies,
        auth=auth,
        callback_url=settings.composio.callback_url,
        kapso=settings.kapso,
        queue_limits=QueueLimits(workers.inbox_concurrency, workers.poll_interval_seconds),
    )
    inbox = InboxClient(inbox_service)

    demo = DemoClient(
        DemoService(
            settings.demo,
            auth=auth,
            policy=payment_policy,
            inbox=inbox,
            payments=payments,
            files=files,
            realtime=realtime,
            seeder=DemoSeeder(payment_policy, DemoSeedRepository(product_sessionmaker)),
            reset_repository=DemoResetRepository(product_sessionmaker),
            registry=ExecutionRegistry(),
            destinations=KitDestinations(
                email_address=settings.demo.inbox_address,
                whatsapp_number=settings.kapso.sandbox_display_number or None,
            ),
            is_guardrail_enforced=guardrails_settings.enforce,
            is_malware_scan_enabled=storage_settings.malware_scan_enabled,
        )
    )
    accountability = AccountabilityClient(
        AccountabilityService(
            AccountabilityRepository(product_sessionmaker), payments, payment_policy
        )
    )

    return Clients(
        auth=auth,
        files=files,
        fx=fx,
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
        demo=demo,
        accountability=accountability,
    )


def _realtime_backend(settings: Settings) -> RealtimeBackend:
    realtime_settings = settings.realtime
    is_realtime_configured = realtime_settings.enabled and bool(realtime_settings.http_domain)
    if not is_realtime_configured:
        return NullRealtimeBackend()
    return AppSyncEventsBackend(realtime_settings)
