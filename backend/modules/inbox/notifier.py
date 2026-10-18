from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.inbox import InboxEmailStatus
from contracts.realtime import RealtimeEvent, RealtimeEventType

if TYPE_CHECKING:
    from clients.realtime import RealtimeClient


class InboxNotifier:
    def __init__(self, realtime: "RealtimeClient") -> None:
        self._realtime = realtime

    async def item_changed(
        self,
        owner_id: UUID,
        item_id: UUID,
        status: InboxEmailStatus,
        run_id: UUID | None = None,
    ) -> None:
        await self._realtime.publish(
            owner_id,
            [
                RealtimeEvent(
                    type=RealtimeEventType.INBOX_ITEM,
                    item_id=item_id,
                    run_id=run_id,
                    step=status.value,
                    payload={"status": status.value},
                    created_at=datetime.now(UTC),
                )
            ],
        )
