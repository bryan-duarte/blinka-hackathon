from collections.abc import Sequence
from itertools import batched
from uuid import UUID

from contracts.realtime import RealtimeEvent
from core.logging_config import get_logger
from modules.realtime.appsync import RealtimeBackend

logger = get_logger(__name__)

MAX_EVENTS_PER_PUBLISH = 5
MAX_EVENT_BYTES = 240 * 1024
OVERSIZED_PAYLOAD = {"truncated": True}


class RealtimeService:
    def __init__(self, backend: RealtimeBackend, namespace: str) -> None:
        self._backend = backend
        self._namespace = namespace

    def channel_for(self, owner_id: UUID) -> str:
        return f"/{self._namespace}/{owner_id}"

    async def publish(self, owner_id: UUID, events: Sequence[RealtimeEvent]) -> None:
        channel = self.channel_for(owner_id)
        serialized_events = [_serialize(event) for event in events]
        for event_batch in batched(serialized_events, MAX_EVENTS_PER_PUBLISH, strict=False):
            try:
                await self._backend.publish(channel, list(event_batch))
            except Exception:
                logger.warning(
                    "realtime_publish_failed",
                    owner_id=owner_id,
                    count=len(event_batch),
                    exc_info=True,
                )


def _serialize(event: RealtimeEvent) -> str:
    serialized_event = event.model_dump_json()
    is_oversized = len(serialized_event.encode()) > MAX_EVENT_BYTES
    if not is_oversized:
        return serialized_event
    return event.model_copy(update={"payload": OVERSIZED_PAYLOAD}).model_dump_json()
