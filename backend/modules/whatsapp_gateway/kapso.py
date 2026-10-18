import hashlib
import hmac
import re
from datetime import UTC, datetime
from pathlib import PurePath

from contracts.files import EVIDENCE_MIME_BY_EXTENSION
from contracts.whatsapp_gateway import WhatsAppDocumentEvent
from modules.whatsapp_gateway.errors import WhatsAppPhoneInvalidError

E164_PHONE = re.compile(r"^\+[1-9]\d{7,14}$")
PHONE_FORMATTING_CHARACTERS = re.compile(r"[\s\-().]")
SHA256_HEX_SIGNATURE = re.compile(r"^[a-f0-9]{64}$", re.IGNORECASE)
DOCUMENT_MESSAGE_TYPE = "document"
INBOUND_DIRECTION = "inbound"


def normalize_phone(raw_phone: str) -> str:
    compact_phone = PHONE_FORMATTING_CHARACTERS.sub("", raw_phone.strip())
    e164_phone = compact_phone if compact_phone.startswith("+") else f"+{compact_phone}"
    if not E164_PHONE.fullmatch(e164_phone):
        raise WhatsAppPhoneInvalidError
    return e164_phone


def normalize_user_phone(raw_phone: str) -> str:
    if not raw_phone.strip().startswith("+"):
        raise WhatsAppPhoneInvalidError
    return normalize_phone(raw_phone)


def is_valid_signature(secret: str, body: bytes, signature: str | None) -> bool:
    is_well_formed = bool(secret) and bool(signature) and SHA256_HEX_SIGNATURE.fullmatch(signature)
    if not is_well_formed:
        return False
    expected_signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_signature, signature.lower())


def iter_message_payloads(webhook_body: object) -> list[dict]:
    if not isinstance(webhook_body, dict):
        return []
    batched_payloads = webhook_body.get("data")
    if isinstance(batched_payloads, list):
        return [payload for payload in batched_payloads if isinstance(payload, dict)]
    return [webhook_body]


def message_type(payload: dict) -> str | None:
    return _mapping(payload, "message").get("type")


def document_event(payload: dict) -> WhatsAppDocumentEvent | None:
    message = _mapping(payload, "message")
    message_metadata = _mapping(message, "kapso")
    conversation = _mapping(payload, "conversation")
    document = _mapping(message, "document")
    media_data = _mapping(message_metadata, "media_data")
    is_inbound_document = (
        message.get("type") == DOCUMENT_MESSAGE_TYPE
        and message_metadata.get("direction") == INBOUND_DIRECTION
    )
    if not is_inbound_document:
        return None
    filename = document.get("filename") or media_data.get("filename") or ""
    mime = EVIDENCE_MIME_BY_EXTENSION.get(PurePath(filename).suffix.lower())
    phone_number_id = payload.get("phone_number_id") or conversation.get("phone_number_id")
    has_routing_keys = bool(message.get("id")) and bool(phone_number_id)
    if mime is None or not has_routing_keys:
        return None
    try:
        sender_phone = normalize_phone(str(conversation.get("phone_number") or ""))
    except WhatsAppPhoneInvalidError:
        return None
    return WhatsAppDocumentEvent(
        phone_number_id=str(phone_number_id),
        message_id=str(message["id"]),
        sender_phone=sender_phone,
        contact_name=_mapping(conversation, "kapso").get("contact_name"),
        filename=filename,
        mime=mime,
        caption=_caption(document, message_metadata),
        media_url=message_metadata.get("media_url") or media_data.get("url"),
        media_id=document.get("id"),
        received_at=_received_at(message.get("timestamp")),
    )


def _caption(document: dict, message_metadata: dict) -> str:
    type_data = _mapping(message_metadata, "message_type_data")
    return document.get("caption") or type_data.get("caption") or ""


def _received_at(unix_timestamp: object) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(str(unix_timestamp)), tz=UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def _mapping(container: dict, key: str) -> dict:
    nested_value = container.get(key)
    return nested_value if isinstance(nested_value, dict) else {}
