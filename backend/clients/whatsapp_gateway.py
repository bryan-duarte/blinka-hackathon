from collections.abc import Mapping
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.mail_gateway import FetchedEmail
from contracts.whatsapp_gateway import KapsoPhoneNumber, KapsoSetupLink, WhatsAppDocumentEvent

if TYPE_CHECKING:
    from modules.whatsapp_gateway.service import WhatsAppGatewayService


class WhatsAppGatewayClient:
    def __init__(self, service: "WhatsAppGatewayService") -> None:
        self._service = service

    async def ensure_customer(self, owner_id: UUID, name: str) -> str:
        return await self._service.ensure_customer(owner_id, name)

    async def create_setup_link(self, customer_id: str) -> KapsoSetupLink:
        return await self._service.create_setup_link(customer_id)

    async def get_phone_number(self, customer_id: str, phone_number_id: str) -> KapsoPhoneNumber:
        return await self._service.get_phone_number(customer_id, phone_number_id)

    async def register_message_webhook(self, phone_number_id: str) -> str:
        return await self._service.register_message_webhook(phone_number_id)

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> list[WhatsAppDocumentEvent]:
        return self._service.parse_webhook(body, headers)

    async def fetch_message(self, event: WhatsAppDocumentEvent) -> FetchedEmail:
        return await self._service.fetch_message(event)
