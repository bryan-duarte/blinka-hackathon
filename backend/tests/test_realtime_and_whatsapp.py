import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from contracts.realtime import RealtimeEvent, RealtimeEventType
from modules.realtime import RealtimeService
from modules.whatsapp_gateway import (
    WhatsAppPhoneInvalidError,
    normalize_phone,
    normalize_user_phone,
)
from modules.whatsapp_gateway.kapso import (
    document_event,
    is_valid_signature,
    iter_message_payloads,
)

WEBHOOK_SECRET = "test-secret"


class RecordingBackend:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    async def publish(self, channel: str, events: list[str]) -> None:
        self.batch_sizes.append(len(events))


class FailingBackend:
    async def publish(self, channel: str, events: list[str]) -> None:
        raise RuntimeError("appsync down")


def _realtime_events(count: int) -> list[RealtimeEvent]:
    return [
        RealtimeEvent(
            type=RealtimeEventType.RUN_STEP,
            step="started",
            sequence=index,
            created_at=datetime.now(UTC),
        )
        for index in range(count)
    ]


def _document_payload(message_type: str = "document", filename: str = "factura.pdf") -> dict:
    return {
        "message": {
            "id": "wamid.1",
            "timestamp": "1730092800",
            "type": message_type,
            "document": {"id": "media-1", "filename": filename, "caption": "Factura octubre"},
            "kapso": {"direction": "inbound", "media_url": "https://api.kapso.ai/media/1"},
        },
        "conversation": {
            "phone_number": "+56 9 1234-5678",
            "kapso": {"contact_name": "Proveedor"},
        },
        "phone_number_id": "597907523413541",
    }


async def test_realtime_publish_splits_events_in_batches_of_five() -> None:
    backend = RecordingBackend()
    await RealtimeService(backend, "inbox").publish(uuid4(), _realtime_events(12))
    assert backend.batch_sizes == [5, 5, 2]


async def test_realtime_publish_never_raises() -> None:
    await RealtimeService(FailingBackend(), "inbox").publish(uuid4(), _realtime_events(3))


def test_realtime_channel_is_per_owner() -> None:
    owner_id = uuid4()
    assert (
        RealtimeService(RecordingBackend(), "inbox").channel_for(owner_id) == f"/inbox/{owner_id}"
    )


def test_webhook_signature_accepts_only_untampered_bodies() -> None:
    body = json.dumps(_document_payload()).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert is_valid_signature(WEBHOOK_SECRET, body, signature)
    assert not is_valid_signature(WEBHOOK_SECRET, body + b" ", signature)
    assert not is_valid_signature(WEBHOOK_SECRET, body, None)
    assert not is_valid_signature("", body, signature)


def test_iter_message_payloads_unwraps_batches_and_singles() -> None:
    single_payload = _document_payload()
    assert iter_message_payloads(single_payload) == [single_payload]
    assert iter_message_payloads({"data": [single_payload, single_payload]}) == [
        single_payload,
        single_payload,
    ]
    assert iter_message_payloads([]) == []


def test_document_event_accepts_inbound_evidence_documents() -> None:
    event = document_event(_document_payload())
    assert event is not None
    assert event.sender_phone == "+56912345678"
    assert event.mime == "application/pdf"
    assert event.media_id == "media-1"
    assert event.caption == "Factura octubre"
    assert event.received_at == datetime.fromtimestamp(1730092800, tz=UTC)


@pytest.mark.parametrize(
    ("message_type", "filename"),
    [("image", "foto.jpg"), ("document", "contrato.docx"), ("audio", "nota.ogg")],
)
def test_document_event_ignores_non_evidence_messages(message_type: str, filename: str) -> None:
    assert document_event(_document_payload(message_type, filename)) is None


def test_document_event_ignores_outbound_echoes() -> None:
    payload = _document_payload()
    payload["message"]["kapso"]["direction"] = "outbound"
    assert document_event(payload) is None


def test_normalize_phone_returns_e164() -> None:
    assert normalize_phone("+56 9 1234-5678") == "+56912345678"
    assert normalize_phone("56 (9) 1234 5678") == "+56912345678"
    with pytest.raises(WhatsAppPhoneInvalidError):
        normalize_phone("12345")


def test_user_phone_requires_country_code() -> None:
    assert normalize_user_phone("+56 9 1234 5678") == "+56912345678"
    with pytest.raises(WhatsAppPhoneInvalidError):
        normalize_user_phone("9 1234 5678")
