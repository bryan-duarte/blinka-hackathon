from uuid import UUID

from fastapi import APIRouter, status

from api.deps import ClientsDep, CurrentUserDep
from contracts.inbox import (
    ConfirmMailboxRequest,
    ConnectMailboxRequest,
    InboxChannel,
    InboxEmailDetail,
    InboxEmailView,
    MailboxConnectionView,
    MailboxConnectStarted,
)
from contracts.whatsapp_gateway import (
    ConfirmWhatsAppRequest,
    RegisterSandboxRequest,
    WhatsAppSandboxView,
)

inbox_router = APIRouter(prefix="/inbox", tags=["inbox"])


@inbox_router.post(
    "/connections", response_model=MailboxConnectStarted, status_code=status.HTTP_201_CREATED
)
async def start_connection(
    request: ConnectMailboxRequest, user: CurrentUserDep, clients: ClientsDep
) -> MailboxConnectStarted:
    return await clients.inbox.start_connection(user, request.provider)


@inbox_router.post("/connections/confirm", response_model=MailboxConnectionView)
async def confirm_connection(
    request: ConfirmMailboxRequest, user: CurrentUserDep, clients: ClientsDep
) -> MailboxConnectionView:
    return await clients.inbox.confirm_connection(user, request.connected_account_id)


@inbox_router.get("/connections", response_model=list[MailboxConnectionView])
async def list_connections(
    user: CurrentUserDep, clients: ClientsDep
) -> list[MailboxConnectionView]:
    return await clients.inbox.list_connections(user)


@inbox_router.post("/whatsapp/sandbox", response_model=WhatsAppSandboxView)
async def register_whatsapp_sandbox(
    request: RegisterSandboxRequest, user: CurrentUserDep, clients: ClientsDep
) -> WhatsAppSandboxView:
    return await clients.inbox.register_whatsapp_sandbox(user, request.phone_number)


@inbox_router.post(
    "/whatsapp/own-number",
    response_model=MailboxConnectStarted,
    status_code=status.HTTP_201_CREATED,
)
async def start_whatsapp_connection(
    user: CurrentUserDep, clients: ClientsDep
) -> MailboxConnectStarted:
    return await clients.inbox.start_whatsapp_connection(user)


@inbox_router.post("/whatsapp/confirm", response_model=MailboxConnectionView)
async def confirm_whatsapp_connection(
    request: ConfirmWhatsAppRequest, user: CurrentUserDep, clients: ClientsDep
) -> MailboxConnectionView:
    return await clients.inbox.confirm_whatsapp_connection(user, request)


@inbox_router.get("/emails", response_model=list[InboxEmailView])
async def list_emails(
    user: CurrentUserDep, clients: ClientsDep, source: InboxChannel | None = None
) -> list[InboxEmailView]:
    return await clients.inbox.list_emails(user, source)


@inbox_router.get("/emails/{email_id}", response_model=InboxEmailDetail)
async def get_email(email_id: UUID, user: CurrentUserDep, clients: ClientsDep) -> InboxEmailDetail:
    return await clients.inbox.get_email(user, email_id)
