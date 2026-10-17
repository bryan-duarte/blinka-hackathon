from collections.abc import Mapping
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.inbox import (
    InboxEmailDetail,
    InboxEmailView,
    MailboxConnectionView,
    MailboxConnectStarted,
    SimulatedEmailKind,
)
from contracts.mail_gateway import MailProvider

if TYPE_CHECKING:
    from modules.inbox.service import InboxService


class InboxClient:
    def __init__(self, service: "InboxService") -> None:
        self._service = service

    async def start_connection(
        self, owner: CurrentUser, provider: MailProvider
    ) -> MailboxConnectStarted:
        return await self._service.start_connection(owner, provider)

    async def confirm_connection(
        self, owner: CurrentUser, connected_account_id: str
    ) -> MailboxConnectionView:
        return await self._service.confirm_connection(owner, connected_account_id)

    async def list_connections(self, owner: CurrentUser) -> list[MailboxConnectionView]:
        return await self._service.list_connections(owner)

    async def ingest_webhook(self, body: bytes, headers: Mapping[str, str]) -> None:
        await self._service.ingest_webhook(body, headers)

    async def simulate(self, owner: CurrentUser, kind: SimulatedEmailKind) -> InboxEmailView:
        return await self._service.simulate(owner, kind)

    async def list_emails(self, owner: CurrentUser) -> list[InboxEmailView]:
        return await self._service.list_emails(owner)

    async def get_email(self, owner: CurrentUser, email_id: UUID) -> InboxEmailDetail:
        return await self._service.get_email(owner, email_id)

    async def fail_unfinished(self, reason: str) -> None:
        await self._service.fail_unfinished(reason)

    async def shutdown(self) -> None:
        await self._service.shutdown()
