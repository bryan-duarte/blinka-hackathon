from collections.abc import Mapping
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.inbox import (
    InboxChannel,
    InboxEmailDetail,
    InboxEmailView,
    MailboxConnectionView,
    MailboxConnectStarted,
    SimulatedEmailKind,
)
from contracts.mail_gateway import MailProvider
from contracts.whatsapp_gateway import ConfirmWhatsAppRequest, WhatsAppSandboxView

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

    async def register_whatsapp_sandbox(
        self, owner: CurrentUser, raw_phone: str
    ) -> WhatsAppSandboxView:
        return await self._service.register_whatsapp_sandbox(owner, raw_phone)

    async def start_whatsapp_connection(self, owner: CurrentUser) -> MailboxConnectStarted:
        return await self._service.start_whatsapp_connection(owner)

    async def confirm_whatsapp_connection(
        self, owner: CurrentUser, request: ConfirmWhatsAppRequest
    ) -> MailboxConnectionView:
        return await self._service.confirm_whatsapp_connection(owner, request)

    async def list_connections(self, owner: CurrentUser) -> list[MailboxConnectionView]:
        return await self._service.list_connections(owner)

    async def ingest_webhook(self, body: bytes, headers: Mapping[str, str]) -> None:
        await self._service.ingest_webhook(body, headers)

    async def ingest_whatsapp_webhook(self, body: bytes, headers: Mapping[str, str]) -> None:
        await self._service.ingest_whatsapp_webhook(body, headers)

    async def simulate(
        self, owner: CurrentUser, kind: SimulatedEmailKind, channel: InboxChannel
    ) -> InboxEmailView:
        return await self._service.simulate(owner, kind, channel)

    async def list_emails(
        self, owner: CurrentUser, source: InboxChannel | None
    ) -> list[InboxEmailView]:
        return await self._service.list_emails(owner, source)

    async def get_email(self, owner: CurrentUser, email_id: UUID) -> InboxEmailDetail:
        return await self._service.get_email(owner, email_id)

    async def fail_unfinished(self, reason: str) -> None:
        await self._service.fail_unfinished(reason)

    async def shutdown(self) -> None:
        await self._service.shutdown()
