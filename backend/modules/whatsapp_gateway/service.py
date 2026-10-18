import json
from collections.abc import Mapping
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from contracts.mail_gateway import FetchedAttachment, FetchedEmail
from contracts.whatsapp_gateway import KapsoPhoneNumber, KapsoSetupLink, WhatsAppDocumentEvent
from core.config import KapsoSettings
from core.logging_config import get_logger
from modules.whatsapp_gateway import kapso
from modules.whatsapp_gateway.errors import (
    WhatsAppNumberUnverifiedError,
    WhatsAppProviderError,
    WhatsAppSignatureError,
)

logger = get_logger(__name__)

KAPSO_PLATFORM_PATH = "/platform/v1"
KAPSO_META_PATH = "/meta/whatsapp/v24.0"
KAPSO_HOST_SUFFIX = "kapso.ai"
SECURE_SCHEME = "https"
API_KEY_HEADER = "X-API-Key"
WEBHOOK_EVENT_HEADER = "x-webhook-event"
WEBHOOK_SIGNATURE_HEADER = "x-webhook-signature"
MESSAGE_RECEIVED_EVENT = "whatsapp.message.received"
KAPSO_WEBHOOK_KIND = "kapso"
WEBHOOK_PAYLOAD_VERSION = "v2"
SETUP_LINK_CONNECTION_TYPES = ["coexistence", "dedicated"]
SETUP_LINK_LANGUAGE = "es"
REQUEST_TIMEOUT_SECONDS = 30
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
RESPONSE_DATA_KEY = "data"
SANDBOX_PHONE_KIND = "sandbox"


class WhatsAppGatewayService:
    def __init__(self, settings: KapsoSettings) -> None:
        self._settings = settings

    async def ensure_customer(self, owner_id: UUID, name: str) -> str:
        customer = await self._request(
            "POST",
            f"{KAPSO_PLATFORM_PATH}/customers",
            json_body={"customer": {"name": name, "external_customer_id": str(owner_id)}},
        )
        return str(customer["id"])

    async def create_setup_link(self, customer_id: str) -> KapsoSetupLink:
        setup_link = await self._request(
            "POST",
            f"{KAPSO_PLATFORM_PATH}/customers/{customer_id}/setup_links",
            json_body={
                "setup_link": {
                    "success_redirect_url": self._settings.callback_url,
                    "failure_redirect_url": self._settings.callback_url,
                    "allowed_connection_types": SETUP_LINK_CONNECTION_TYPES,
                    "language": SETUP_LINK_LANGUAGE,
                }
            },
        )
        return KapsoSetupLink(setup_link_id=str(setup_link["id"]), url=setup_link["url"])

    async def get_phone_number(self, customer_id: str, phone_number_id: str) -> KapsoPhoneNumber:
        phone_numbers = await self.list_phone_numbers(
            {"customer_id": customer_id, "phone_number_id": phone_number_id}
        )
        for phone_number in phone_numbers:
            is_owned_number = (
                phone_number.phone_number_id == phone_number_id
                and phone_number.customer_id == customer_id
            )
            if is_owned_number:
                return phone_number
        raise WhatsAppNumberUnverifiedError

    async def list_phone_numbers(
        self, filters: Mapping[str, str] | None = None
    ) -> list[KapsoPhoneNumber]:
        phone_numbers = await self._request(
            "GET", f"{KAPSO_PLATFORM_PATH}/whatsapp/phone_numbers", params=filters
        )
        return [
            KapsoPhoneNumber(
                phone_number_id=str(phone_number["phone_number_id"]),
                customer_id=phone_number.get("customer_id"),
                display_phone_number=phone_number.get("display_phone_number"),
                is_coexistence=bool(phone_number.get("is_coexistence")),
                is_sandbox=phone_number.get("kind") == SANDBOX_PHONE_KIND,
            )
            for phone_number in phone_numbers
        ]

    async def list_message_webhook_urls(self, phone_number_id: str) -> list[str]:
        webhooks = await self._request(
            "GET", f"{KAPSO_PLATFORM_PATH}/whatsapp/phone_numbers/{phone_number_id}/webhooks"
        )
        return [webhook.get("url", "") for webhook in webhooks]

    async def register_message_webhook(self, phone_number_id: str) -> str:
        if not self._settings.webhook_url:
            raise WhatsAppProviderError("webhook url not configured")
        webhook = await self._request(
            "POST",
            f"{KAPSO_PLATFORM_PATH}/whatsapp/phone_numbers/{phone_number_id}/webhooks",
            json_body={
                "whatsapp_webhook": {
                    "url": self._settings.webhook_url,
                    "secret_key": self._settings.webhook_secret.get_secret_value(),
                    "events": [MESSAGE_RECEIVED_EVENT],
                    "kind": KAPSO_WEBHOOK_KIND,
                    "payload_version": WEBHOOK_PAYLOAD_VERSION,
                    "active": True,
                    "buffer_enabled": False,
                }
            },
        )
        return str(webhook["id"])

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> list[WhatsAppDocumentEvent]:
        secret = self._settings.webhook_secret.get_secret_value()
        if not kapso.is_valid_signature(secret, body, headers.get(WEBHOOK_SIGNATURE_HEADER)):
            raise WhatsAppSignatureError
        if headers.get(WEBHOOK_EVENT_HEADER) != MESSAGE_RECEIVED_EVENT:
            return []
        try:
            webhook_body = json.loads(body)
        except json.JSONDecodeError:
            logger.warning("whatsapp_webhook_malformed")
            return []
        document_events = []
        for payload in kapso.iter_message_payloads(webhook_body):
            document_event = kapso.document_event(payload)
            if document_event is None:
                logger.debug("whatsapp_message_ignored", message_type=kapso.message_type(payload))
                continue
            document_events.append(document_event)
        return document_events

    async def fetch_message(self, event: WhatsAppDocumentEvent) -> FetchedEmail:
        sender = (
            f"{event.contact_name} <{event.sender_phone}>"
            if event.contact_name
            else event.sender_phone
        )
        return FetchedEmail(
            sender=sender,
            subject=event.filename,
            body=event.caption,
            received_at=event.received_at,
            attachments=[await self._download(event)],
        )

    async def _download(self, event: WhatsAppDocumentEvent) -> FetchedAttachment:
        if event.media_id is not None:
            media = await self._request(
                "GET",
                f"{KAPSO_META_PATH}/{event.media_id}",
                params={"phone_number_id": event.phone_number_id},
            )
            content = await self._get_bytes(media["download_url"], with_api_key=False)
        elif event.media_url is not None:
            content = await self._get_bytes(
                event.media_url, with_api_key=_is_kapso_url(event.media_url)
            )
        else:
            raise WhatsAppProviderError("document has no media reference")
        if len(content) > MAX_DOCUMENT_BYTES:
            raise WhatsAppProviderError("document too large")
        return FetchedAttachment(filename=event.filename, mime=event.mime, content=content)

    async def _get_bytes(self, url: str, with_api_key: bool) -> bytes:
        if urlsplit(url).scheme != SECURE_SCHEME:
            raise WhatsAppProviderError("insecure media url")
        headers = self._auth_headers() if with_api_key else {}
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http_client:
                response = await http_client.get(url, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise WhatsAppProviderError from error
        return response.content

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict | None = None,
        params: Mapping[str, str] | None = None,
    ) -> dict | list:
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http_client:
                response = await http_client.request(
                    method,
                    f"{self._settings.base_url}{path}",
                    json=json_body,
                    params=params,
                    headers=self._auth_headers(),
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            logger.warning("kapso_request_failed", method=method, path=path)
            raise WhatsAppProviderError from error
        response_body = response.json()
        if isinstance(response_body, dict) and RESPONSE_DATA_KEY in response_body:
            return response_body[RESPONSE_DATA_KEY]
        return response_body

    def _auth_headers(self) -> dict[str, str]:
        return {API_KEY_HEADER: self._settings.api_key.get_secret_value()}


def _is_kapso_url(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host == KAPSO_HOST_SUFFIX or host.endswith(f".{KAPSO_HOST_SUFFIX}")
