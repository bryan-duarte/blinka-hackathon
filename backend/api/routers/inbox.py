from uuid import UUID

from fastapi import APIRouter, status

from api.deps import ClientsDep, CurrentUserDep
from contracts.inbox import (
    ConfirmMailboxRequest,
    ConnectMailboxRequest,
    InboxEmailDetail,
    InboxEmailView,
    MailboxConnectionView,
    MailboxConnectStarted,
    SimulateEmailRequest,
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


@inbox_router.get("/emails", response_model=list[InboxEmailView])
async def list_emails(user: CurrentUserDep, clients: ClientsDep) -> list[InboxEmailView]:
    return await clients.inbox.list_emails(user)


@inbox_router.get("/emails/{email_id}", response_model=InboxEmailDetail)
async def get_email(email_id: UUID, user: CurrentUserDep, clients: ClientsDep) -> InboxEmailDetail:
    return await clients.inbox.get_email(user, email_id)


@inbox_router.post("/simulate", response_model=InboxEmailView, status_code=status.HTTP_202_ACCEPTED)
async def simulate_email(
    request: SimulateEmailRequest, user: CurrentUserDep, clients: ClientsDep
) -> InboxEmailView:
    return await clients.inbox.simulate(user, request.kind)
