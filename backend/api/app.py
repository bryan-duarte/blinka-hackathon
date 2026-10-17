from collections.abc import AsyncIterator
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
from modules.auth.errors import EmailTakenError, InvalidCredentialsError
from modules.bills.errors import BillMissingError, BillSourceMissingError, BillStateConflictError
from modules.files.errors import FileMissingError, StorageError
from modules.guardrails.errors import GuardrailRejectionError, GuardrailUnavailableError
from modules.inbox.errors import EmailMissingError, MailboxConnectionMissingError
from modules.mail_gateway.errors import (
    MailboxAlreadyConnectedError,
    MailProviderError,
    WebhookSignatureError,
)
from modules.orchestrator.errors import AgentProviderError
from modules.payment_policy.errors import (
    BlacklistEntryMissingError,
    IdentifierMissingError,
    IdentifierTakenError,
    PayeeInUseError,
    PayeeMissingError,
    PayeeNameTakenError,
    PayeeVersionConflictError,
    PolicyMissingError,
)
from modules.payments.errors import BillNotReviewableError, DecisionMissingError, RunNotFoundError
from modules.sessions.errors import SessionMissingError

logger = get_logger(__name__)

RESTART_INTERRUPTION_REASON = "interrupted by restart"
PAYMENT_DOMAIN_ERROR_RESPONSES: dict[type[Exception], tuple[int, str]] = {
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
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(settings.log_format)
    pools = build_pools(
        settings.product_database_url,
        settings.agent_database_url,
        settings.payments_database_url,
    )
    checkpointers = Checkpointers(settings.agent_database_url, settings.payments_database_url)
    await checkpointers.open()
    try:
        clients = await build_clients(settings, pools, checkpointers)
        await clients.files.ensure_bucket()
        await clients.payments.fail_unfinished(RESTART_INTERRUPTION_REASON)
        await clients.payments.recover_unfinished_payments()
        await clients.inbox.fail_unfinished(RESTART_INTERRUPTION_REASON)
        app.state.settings = settings
        app.state.pools = pools
        app.state.clients = clients
        logger.info("guardrails_configured", enforce=settings.guardrails.enforce)
        logger.info("backend_started")
        yield
    finally:
        clients = getattr(app.state, "clients", None)
        if clients is not None:
            await clients.inbox.shutdown()
            await clients.payments.shutdown_runs()
        await checkpointers.close()
        await pools.product.engine.dispose()
        await pools.agent.engine.dispose()
        await pools.payments.engine.dispose()
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
    app.add_exception_handler(EmailTakenError, _reject_taken_email)
    app.add_exception_handler(SessionMissingError, _reject_missing_session)
    app.add_exception_handler(FileMissingError, _reject_missing_file)
    app.add_exception_handler(RunNotFoundError, _reject_missing_run)
    app.add_exception_handler(StorageError, _reject_storage_down)
    app.add_exception_handler(AgentProviderError, _reject_agent_provider_down)
    app.add_exception_handler(GuardrailUnavailableError, _reject_guardrails_down)
    app.add_exception_handler(WebhookSignatureError, _reject_invalid_webhook)
    app.add_exception_handler(MailboxConnectionMissingError, _reject_missing_mailbox_connection)
    app.add_exception_handler(EmailMissingError, _reject_missing_email)
    app.add_exception_handler(MailboxAlreadyConnectedError, _reject_connected_mailbox)
    app.add_exception_handler(MailProviderError, _reject_mail_provider_down)
    for error_type, (status_code, detail) in PAYMENT_DOMAIN_ERROR_RESPONSES.items():
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


def _reject_taken_email(request: Request, error: EmailTakenError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "email already registered"},
    )


def _reject_missing_session(request: Request, error: SessionMissingError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"detail": "session not found"}
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


def _reject_agent_provider_down(request: Request, error: AgentProviderError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "agent provider unavailable"},
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
