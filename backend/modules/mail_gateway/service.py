import asyncio
from collections.abc import Mapping
from pathlib import PurePath
from uuid import UUID

import httpx
from composio import Composio
from composio.exceptions import (
    ComposioError,
    ComposioMultipleConnectedAccountsError,
    ValidationError,
    WebhookPayloadError,
    WebhookSignatureVerificationError,
)
from composio_client import APIError

from contracts.files import EVIDENCE_MIME_BY_EXTENSION
from contracts.mail_gateway import (
    FetchedAttachment,
    FetchedEmail,
    MailAccountStatus,
    MailboxLink,
    MailProvider,
    MailTriggerEvent,
)
from core.config import ComposioSettings
from core.logging_config import get_logger
from modules.mail_gateway import gmail, outlook
from modules.mail_gateway.errors import (
    MailboxAlreadyConnectedError,
    MailProviderError,
    WebhookSignatureError,
)

logger = get_logger(__name__)

GMAIL_NEW_MESSAGE_TRIGGER = "GMAIL_NEW_GMAIL_MESSAGE"
OUTLOOK_NEW_MESSAGE_TRIGGER = "OUTLOOK_MESSAGE_TRIGGER"
GMAIL_GET_ATTACHMENT_TOOL = "GMAIL_GET_ATTACHMENT"
OUTLOOK_GET_MESSAGE_TOOL = "OUTLOOK_GET_MESSAGE"
OUTLOOK_LIST_ATTACHMENTS_TOOL = "OUTLOOK_LIST_OUTLOOK_ATTACHMENTS"
TRIGGER_PROVIDERS = {
    GMAIL_NEW_MESSAGE_TRIGGER: MailProvider.GMAIL,
    OUTLOOK_NEW_MESSAGE_TRIGGER: MailProvider.OUTLOOK,
}
NEW_MESSAGE_TRIGGERS = {provider: slug for slug, provider in TRIGGER_PROVIDERS.items()}
ACCOUNT_STATUSES = {
    "ACTIVE": MailAccountStatus.ACTIVE,
    "INITIALIZING": MailAccountStatus.INITIATED,
    "INITIATED": MailAccountStatus.INITIATED,
    "FAILED": MailAccountStatus.FAILED,
    "EXPIRED": MailAccountStatus.EXPIRED,
    "INACTIVE": MailAccountStatus.EXPIRED,
    "REVOKED": MailAccountStatus.EXPIRED,
}
CURRENT_MAILBOX_USER = "me"
GMAIL_INBOX_LABEL = "INBOX"
OUTLOOK_INBOX_FOLDER = "inbox"
OUTLOOK_FULL_RESPONSE_DETAIL = "full"
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ATTACHMENT_DOWNLOAD_TIMEOUT_SECONDS = 30
SDK_ERRORS = (ComposioError, APIError, httpx.HTTPError)
WEBHOOK_REJECTION_ERRORS = (
    ValidationError,
    WebhookSignatureVerificationError,
    WebhookPayloadError,
)


class MailGatewayService:
    def __init__(self, settings: ComposioSettings) -> None:
        self._settings = settings
        self._composio: Composio | None = None

    def _sdk(self) -> Composio:
        if self._composio is None:
            try:
                self._composio = Composio(api_key=self._settings.api_key.get_secret_value())
            except ComposioError as error:
                raise MailProviderError from error
        return self._composio

    async def link_account(
        self, user_id: UUID, provider: MailProvider, callback_url: str
    ) -> MailboxLink:
        sdk = self._sdk()
        try:
            connection_request = await asyncio.to_thread(
                sdk.connected_accounts.link,
                str(user_id),
                self._auth_config_id(provider),
                callback_url=callback_url,
            )
        except ComposioMultipleConnectedAccountsError as error:
            raise MailboxAlreadyConnectedError from error
        except SDK_ERRORS as error:
            raise MailProviderError from error
        if not connection_request.redirect_url:
            raise MailProviderError
        return MailboxLink(
            connected_account_id=connection_request.id,
            redirect_url=connection_request.redirect_url,
        )

    async def get_account_status(self, connected_account_id: str) -> MailAccountStatus:
        sdk = self._sdk()
        try:
            connected_account = await asyncio.to_thread(
                sdk.connected_accounts.get, connected_account_id
            )
        except SDK_ERRORS as error:
            raise MailProviderError from error
        return ACCOUNT_STATUSES.get(connected_account.status, MailAccountStatus.FAILED)

    async def enable_new_mail_trigger(
        self, user_id: UUID, provider: MailProvider, connected_account_id: str
    ) -> str:
        sdk = self._sdk()
        try:
            trigger = await asyncio.to_thread(
                sdk.triggers.create,
                NEW_MESSAGE_TRIGGERS[provider],
                user_id=str(user_id),
                connected_account_id=connected_account_id,
                trigger_config=self._trigger_config(provider),
            )
        except SDK_ERRORS as error:
            raise MailProviderError from error
        logger.info("mail_trigger_enabled", provider=provider, trigger_id=trigger.trigger_id)
        return trigger.trigger_id

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> MailTriggerEvent | None:
        webhook_secret = self._settings.webhook_secret.get_secret_value()
        if not webhook_secret:
            logger.warning("composio_webhook_rejected", reason="webhook secret not configured")
            raise WebhookSignatureError
        try:
            verified_webhook = self._sdk().triggers.parse(
                body=body, headers=dict(headers), verify_secret=webhook_secret
            )
        except WEBHOOK_REJECTION_ERRORS as error:
            logger.warning("composio_webhook_rejected", reason=type(error).__name__)
            raise WebhookSignatureError from error
        trigger_event = verified_webhook.get("payload") or {}
        provider = TRIGGER_PROVIDERS.get(trigger_event.get("trigger_slug"))
        if provider is None:
            logger.info("composio_webhook_ignored", trigger_slug=trigger_event.get("trigger_slug"))
            return None
        trigger_data = trigger_event.get("payload") or {}
        message_id = _message_id(provider, trigger_data)
        if not message_id:
            logger.warning("composio_webhook_ignored", reason="message id missing")
            return None
        metadata = trigger_event.get("metadata") or {}
        connected_account = metadata.get("connected_account") or {}
        user_id = trigger_event.get("user_id")
        connected_account_id = connected_account.get("id")
        if not user_id or not connected_account_id:
            logger.warning("composio_webhook_ignored", reason="incomplete trigger payload")
            return None
        return MailTriggerEvent(
            provider=provider,
            user_id=user_id,
            connected_account_id=connected_account_id,
            message_id=message_id,
            data=trigger_data,
        )

    async def fetch_email(self, event: MailTriggerEvent) -> FetchedEmail:
        if event.provider == MailProvider.OUTLOOK:
            return await self._fetch_outlook(event)
        return await self._fetch_gmail(event)

    async def _fetch_gmail(self, event: MailTriggerEvent) -> FetchedEmail:
        trigger_data = event.data
        attachment_list = trigger_data.get("attachment_list") or []
        logger.info(
            "gmail_event_shape",
            data_keys=sorted(trigger_data),
            attachment_keys=[sorted(attachment) for attachment in attachment_list],
        )
        downloaded_attachments = [
            await self._download_gmail_attachment(event, attachment_id, filename)
            for attachment_id, filename in gmail.evidence_attachments(attachment_list)
        ]
        attachments = [attachment for attachment in downloaded_attachments if attachment]
        return FetchedEmail(
            sender=trigger_data.get("sender") or "",
            subject=trigger_data.get("subject") or "",
            body=trigger_data.get("message_text") or "",
            received_at=gmail.parse_timestamp(trigger_data.get("message_timestamp")),
            attachments=attachments,
        )

    async def _download_gmail_attachment(
        self, event: MailTriggerEvent, attachment_id: str, filename: str
    ) -> FetchedAttachment | None:
        tool_data = await self._execute_tool(
            GMAIL_GET_ATTACHMENT_TOOL,
            {
                "message_id": event.message_id,
                "attachment_id": attachment_id,
                "file_name": filename,
                "user_id": CURRENT_MAILBOX_USER,
            },
            event,
            self._settings.gmail_toolkit_version,
        )
        s3url = gmail.find_s3url(tool_data)
        if s3url is None:
            raise MailProviderError
        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(s3url, timeout=ATTACHMENT_DOWNLOAD_TIMEOUT_SECONDS)
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise MailProviderError from error
        return _sized_attachment(filename, response.content)

    async def _fetch_outlook(self, event: MailTriggerEvent) -> FetchedEmail:
        message_data = await self._execute_tool(
            OUTLOOK_GET_MESSAGE_TOOL,
            {"message_id": event.message_id, "user_id": CURRENT_MAILBOX_USER},
            event,
            self._settings.outlook_toolkit_version,
        )
        message = outlook.graph_response(message_data)
        attachments = []
        if message.get("hasAttachments"):
            attachments = await self._outlook_evidence_attachments(event)
        return FetchedEmail(
            sender=outlook.sender(message),
            subject=message.get("subject") or "",
            body=outlook.body_text(message),
            received_at=outlook.received_at(message),
            attachments=attachments,
        )

    async def _outlook_evidence_attachments(
        self, event: MailTriggerEvent
    ) -> list[FetchedAttachment]:
        attachments_data = await self._execute_tool(
            OUTLOOK_LIST_ATTACHMENTS_TOOL,
            {"message_id": event.message_id, "response_detail": OUTLOOK_FULL_RESPONSE_DETAIL},
            event,
            self._settings.outlook_toolkit_version,
        )
        sized_attachments = [
            _sized_attachment(attachment.filename, attachment.content)
            for attachment in outlook.evidence_attachments(attachments_data)
        ]
        return [attachment for attachment in sized_attachments if attachment]

    async def _execute_tool(
        self, tool_slug: str, arguments: dict, event: MailTriggerEvent, version: str
    ) -> dict:
        sdk = self._sdk()
        try:
            execution = await asyncio.to_thread(
                sdk.tools.execute,
                tool_slug,
                arguments,
                user_id=event.user_id,
                connected_account_id=event.connected_account_id,
                version=version,
            )
        except SDK_ERRORS as error:
            raise MailProviderError from error
        if not execution["successful"]:
            logger.warning("mail_tool_failed", tool=tool_slug, error=execution["error"])
            raise MailProviderError
        return execution["data"]

    def _auth_config_id(self, provider: MailProvider) -> str:
        auth_config_ids = {
            MailProvider.GMAIL: self._settings.gmail_auth_config_id,
            MailProvider.OUTLOOK: self._settings.outlook_auth_config_id,
        }
        auth_config_id = auth_config_ids.get(provider)
        if not auth_config_id:
            logger.error("mail_auth_config_missing", provider=provider)
            raise MailProviderError
        return auth_config_id

    def _trigger_config(self, provider: MailProvider) -> dict:
        if provider == MailProvider.OUTLOOK:
            return {"folder_id": OUTLOOK_INBOX_FOLDER}
        return {
            "labelIds": GMAIL_INBOX_LABEL,
            "interval": self._settings.gmail_poll_interval_minutes,
        }


def _message_id(provider: MailProvider, trigger_data: dict) -> str:
    if provider == MailProvider.OUTLOOK:
        return str(trigger_data.get("id") or "")
    return gmail.message_id(trigger_data)


def _sized_attachment(filename: str, content: bytes) -> FetchedAttachment | None:
    if len(content) > MAX_ATTACHMENT_BYTES:
        logger.info("mail_attachment_skipped", filename=filename, size_bytes=len(content))
        return None
    mime = EVIDENCE_MIME_BY_EXTENSION[PurePath(filename).suffix.lower()]
    return FetchedAttachment(filename=filename, mime=mime, content=content)
