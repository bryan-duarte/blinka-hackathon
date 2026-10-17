from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from api.routers import api_router
from container import build_clients
from core.config import Settings
from core.db import Checkpointers, build_pools
from core.logging_config import configure_logging, get_logger
from modules.auth.errors import EmailTakenError, InvalidCredentialsError
from modules.files.errors import FileMissingError, StorageError
from modules.guardrails.errors import GuardrailRejectionError
from modules.orchestrator.errors import AgentProviderError
from modules.payments.errors import RunNotFoundError
from modules.sessions.errors import SessionMissingError

logger = get_logger(__name__)

RESTART_INTERRUPTION_REASON = "interrupted by restart"


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
        app.state.settings = settings
        app.state.pools = pools
        app.state.clients = clients
        logger.info("backend_started")
        yield
    finally:
        clients = getattr(app.state, "clients", None)
        if clients is not None:
            await clients.payments.shutdown_runs()
        await checkpointers.close()
        await pools.product.engine.dispose()
        await pools.agent.engine.dispose()
        await pools.payments.engine.dispose()
        logger.info("backend_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Blinka API", lifespan=lifespan)
    app.add_exception_handler(GuardrailRejectionError, _reject_unsafe_input)
    app.add_exception_handler(InvalidCredentialsError, _reject_invalid_credentials)
    app.add_exception_handler(EmailTakenError, _reject_taken_email)
    app.add_exception_handler(SessionMissingError, _reject_missing_session)
    app.add_exception_handler(FileMissingError, _reject_missing_file)
    app.add_exception_handler(RunNotFoundError, _reject_missing_run)
    app.add_exception_handler(StorageError, _reject_storage_down)
    app.add_exception_handler(AgentProviderError, _reject_agent_provider_down)
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


app = create_app()
