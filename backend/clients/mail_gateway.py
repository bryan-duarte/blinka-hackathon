from collections.abc import Mapping
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.mail_gateway import (
    FetchedEmail,
    MailAccountStatus,
    MailboxLink,
    MailProvider,
    MailTriggerEvent,
)

if TYPE_CHECKING:
    from modules.mail_gateway.service import MailGatewayService


class MailGatewayClient:
    def __init__(self, service: "MailGatewayService") -> None:
        self._service = service

    async def link_account(
        self, user_id: UUID, provider: MailProvider, callback_url: str
    ) -> MailboxLink:
        return await self._service.link_account(user_id, provider, callback_url)

    async def get_account_status(self, connected_account_id: str) -> MailAccountStatus:
        return await self._service.get_account_status(connected_account_id)

    async def enable_new_mail_trigger(
        self, user_id: UUID, provider: MailProvider, connected_account_id: str
    ) -> str:
        return await self._service.enable_new_mail_trigger(user_id, provider, connected_account_id)

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> MailTriggerEvent | None:
        return self._service.parse_webhook(body, headers)

    async def fetch_email(self, event: MailTriggerEvent) -> FetchedEmail:
        return await self._service.fetch_email(event)
