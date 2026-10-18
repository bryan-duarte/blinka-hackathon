from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.realtime import RealtimeEvent

if TYPE_CHECKING:
    from modules.realtime.service import RealtimeService


class RealtimeClient:
    def __init__(self, service: "RealtimeService") -> None:
        self._service = service

    async def publish(self, owner_id: UUID, events: Sequence[RealtimeEvent]) -> None:
        await self._service.publish(owner_id, events)
