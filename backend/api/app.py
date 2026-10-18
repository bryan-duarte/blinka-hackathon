import asyncio
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import api_router
from container import build_clients
from core.config import CorsSettings, Settings
from core.db import Checkpointers, build_pools
from core.logging_config import configure_logging, get_logger
from modules.auth.errors import InvalidCredentialsError
from modules.bills.errors import BillMissingError, BillSourceMissingError, BillStateConflictError
from modules.demo.errors import (
    DemoAccessDeniedError,
    DemoBusyError,
    DemoDisabledError,
    DemoLaunchLimitError,
    DemoLaunchMissingError,
    DemoResetFailedError,
    DemoScenarioMissingError,
    DemoScenarioUnavailableError,
)
from modules.files.errors import (
    FileMissingError,
    FileQuarantinedError,
    StorageError,
    UnsafeArchiveError,
    UnsupportedFileError,
)
from modules.guardrails.errors import GuardrailRejectionError, GuardrailUnavailableError
from modules.inbox.errors import (
    EmailMissingError,
    MailboxConnectionMissingError,
    WhatsAppPhoneTakenError,
)
from modules.mail_gateway.errors import (
    MailboxAlreadyConnectedError,
    MailProviderError,
    WebhookSignatureError,
)
from modules.memory import MemoryNotFoundError, build_memory_index
from modules.payment_policy.errors import (
    BlacklistEntryMissingError,
    IdentifierMissingError,
    IdentifierTakenError,
    PayeeInUseError,
    PayeeMissingError,
    PayeeNameTakenError,
    PayeeVersionConflictError,
    PolicyMissingError,
    TrustedForwarderMissingError,
)
from modules.payments.errors import BillNotReviewableError, DecisionMissingError, RunNotFoundError
from modules.whatsapp_gateway.errors import (
    WhatsAppNumberUnverifiedError,
    WhatsAppPhoneInvalidError,
    WhatsAppProviderError,
    WhatsAppSignatureError,
)

logger = get_logger(__name__)

RESTART_INTERRUPTION_REASON = "interrupted by restart"
BLOCKING_IO_THREAD_PREFIX = "blocking-io"
DOMAIN_ERROR_RESPONSES: dict[type[Exception], tuple[int, str]] = {
    PolicyMissingError: (status.HTTP_404_NOT_FOUND, "payment policy not configured"),
    PayeeMissingError: (status.HTTP_404_NOT_FOUND, "payee not found"),
    IdentifierMissingError: (status.HTTP_404_NOT_FOUND, "identifier not found"),
    BlacklistEntryMissingError: (status.HTTP_404_NOT_FOUND, "blacklist entry not found"),
    BillMissingError: (status.HTTP_404_NOT_FOUND, "bill not found"),
    BillSourceMissingError: (status.HTTP_404_NOT_FOUND, "bill source not found"),
    DecisionMissingError: (status.HTTP_404_NOT_FOUND, "bill decision not found"),
    PayeeVersionConflictError: (status.HTTP_409_CONFLICT, "payee was modified, reload and retry"),
    IdentifierTakenError: (status.HTTP_409_CONFLICT, "identifier belongs to another payee"),
    PayeeNameTakenError: (status.HTTP_409_CONFLICT, "payee name already registered"),
    PayeeInUseError: (status.HTTP_409_CONFLICT, "payee has bills; blacklist it instead"),
    BillStateConflictError: (status.HTTP_409_CONFLICT, "bill is not in the expected state"),
    BillNotReviewableError: (status.HTTP_409_CONFLICT, "bill is not awaiting review"),
    FileQuarantinedError: (status.HTTP_403_FORBIDDEN, "file did not pass the malware scan"),
    UnsupportedFileError: (
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        "file content does not match its type",
    ),
    UnsafeArchiveError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "archive could not be safely expanded",
    ),
    WhatsAppSignatureError: (status.HTTP_401_UNAUTHORIZED, "invalid webhook signature"),
    WhatsAppProviderError: (status.HTTP_502_BAD_GATEWAY, "whatsapp provider unavailable"),
    WhatsAppPhoneInvalidError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid phone number"),
    WhatsAppNumberUnverifiedError: (status.HTTP_409_CONFLICT, "whatsapp number not verified"),
    WhatsAppPhoneTakenError: (status.HTTP_409_CONFLICT, "phone already registered"),
    TrustedForwarderMissingError: (status.HTTP_404_NOT_FOUND, "trusted forwarder not found"),
    DemoDisabledError: (status.HTTP_404_NOT_FOUND, "demo mode is disabled"),
    DemoAccessDeniedError: (status.HTTP_403_FORBIDDEN, "only the demo account can do this"),
    DemoScenarioMissingError: (status.HTTP_404_NOT_FOUND, "demo scenario not found"),
    DemoLaunchMissingError: (status.HTTP_404_NOT_FOUND, "demo launch not found"),
    DemoBusyError: (status.HTTP_409_CONFLICT, "demo is resetting, try again"),
    DemoResetFailedError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "demo reset failed"),
    DemoLaunchLimitError: (status.HTTP_429_TOO_MANY_REQUESTS, "too many demo scenarios running"),
    MemoryNotFoundError: (status.HTTP_404_NOT_FOUND, "memory not found"),
    DemoScenarioUnavailableError: (
        status.HTTP_409_CONFLICT,
        "enable the malware scan to run this scenario",
    ),
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(settings.log_format)
    workers = settings.workers
    asyncio.get_running_loop().set_default_executor(
        ThreadPoolExecutor(
            max_workers=workers.blocking_io_threads, thread_name_prefix=BLOCKING_IO_THREAD_PREFIX
        )
    )
    pools = build_pools(
        settings.product_database_url,
        settings.agent_database_url,
        workers.db_pool_size,
        workers.db_max_overflow,
    )
    store_index = build_memory_index(settings.memory) if settings.memory.enabled else None
    checkpointers = Checkpointers(
        settings.agent_database_url, workers.checkpointer_pool_size, store_index
    )
    await checkpointers.open()
    try:
        clients = await build_clients(settings, pools, checkpointers)
        await clients.payments.fail_unfinished(RESTART_INTERRUPTION_REASON)
        await clients.payments.recover_unfinished_payments()
        await clients.inbox.fail_unfinished(RESTART_INTERRUPTION_REASON)
        if settings.demo.enabled:
            await clients.demo.ensure_demo_account()
        clients.payments.start_worker()
        clients.inbox.start_worker()
        app.state.settings = settings
        app.state.pools = pools
        app.state.clients = clients
        logger.info("guardrails_configured", enforce=settings.guardrails.enforce)
        logger.info(
            "demo_mode_configured", enabled=settings.demo.enabled, email=settings.demo.email
        )
        logger.info("backend_started")
        yield
    finally:
        clients = getattr(app.state, "clients", None)
        if clients is not None:
            await clients.demo.shutdown()
            await clients.inbox.shutdown()
            await clients.payments.shutdown_runs()
            await clients.memory.shutdown()
        await checkpointers.close()
        await pools.product.engine.dispose()
        await pools.agent.engine.dispose()
        logger.info("backend_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Blinka API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CorsSettings().allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(GuardrailRejectionError, _reject_unsafe_input)
    app.add_exception_handler(InvalidCredentialsError, _reject_invalid_credentials)
    app.add_exception_handler(FileMissingError, _reject_missing_file)
    app.add_exception_handler(RunNotFoundError, _reject_missing_run)
    app.add_exception_handler(StorageError, _reject_storage_down)
    app.add_exception_handler(GuardrailUnavailableError, _reject_guardrails_down)
    app.add_exception_handler(WebhookSignatureError, _reject_invalid_webhook)
    app.add_exception_handler(MailboxConnectionMissingError, _reject_missing_mailbox_connection)
    app.add_exception_handler(EmailMissingError, _reject_missing_email)
    app.add_exception_handler(MailboxAlreadyConnectedError, _reject_connected_mailbox)
    app.add_exception_handler(MailProviderError, _reject_mail_provider_down)
    for error_type, (status_code, detail) in DOMAIN_ERROR_RESPONSES.items():
        app.add_exception_handler(error_type, partial(_reject_domain_error, status_code, detail))
    app.include_router(api_router)
    return app


def _reject_unsafe_input(request: Request, error: GuardrailRejectionError) -> JSONResponse:
    violations = [
        {"code": violation.code, "message": violation.message}
        for violation in error.verdict.violations
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"violations": violations},
    )


def _reject_invalid_credentials(request: Request, error: InvalidCredentialsError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "invalid credentials"}
    )


def _reject_missing_file(request: Request, error: FileMissingError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "file not found"})


def _reject_missing_run(request: Request, error: RunNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "run not found"})


def _reject_storage_down(request: Request, error: StorageError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "storage unavailable"},
    )


def _reject_guardrails_down(request: Request, error: GuardrailUnavailableError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "guardrails unavailable"},
    )


def _reject_invalid_webhook(request: Request, error: WebhookSignatureError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "invalid webhook signature"},
    )


def _reject_missing_mailbox_connection(
    request: Request, error: MailboxConnectionMissingError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "mailbox connection not found"},
    )


def _reject_missing_email(request: Request, error: EmailMissingError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"detail": "email not found"}
    )


def _reject_connected_mailbox(
    request: Request, error: MailboxAlreadyConnectedError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT, content={"detail": "mailbox already connected"}
    )


def _reject_mail_provider_down(request: Request, error: MailProviderError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": "mail provider unavailable"},
    )


def _reject_domain_error(
    status_code: int, detail: str, request: Request, error: Exception
) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


app = create_app()
