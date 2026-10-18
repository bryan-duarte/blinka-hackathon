from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.inbox import InboxEmailStatus
from contracts.pipeline import PipelineStage, PipelineStageRecord, PipelineStageStatus
from contracts.realtime import RealtimeEvent, RealtimeEventType
from modules.inbox.repository import InboxRepository

if TYPE_CHECKING:
    from clients.realtime import RealtimeClient

STAGE_STARTED_STATUS: PipelineStageStatus = "started"


class InboxNotifier:
    def __init__(self, realtime: "RealtimeClient", repository: InboxRepository) -> None:
        self._realtime = realtime
        self._repository = repository

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

    async def stage(
        self,
        owner_id: UUID,
        item_id: UUID,
        stage: PipelineStage,
        status: PipelineStageStatus,
        duration_ms: int | None = None,
        detail: dict | None = None,
    ) -> None:
        stage_record = PipelineStageRecord(
            stage=stage,
            status=status,
            duration_ms=duration_ms,
            detail=detail or {},
            at=datetime.now(UTC),
        )
        if status != STAGE_STARTED_STATUS:
            await self._repository.append_stage(item_id, stage_record.model_dump(mode="json"))
        await self._realtime.publish(
            owner_id,
            [
                RealtimeEvent(
                    type=RealtimeEventType.PIPELINE_STAGE,
                    item_id=item_id,
                    step=stage.value,
                    payload=stage_record.model_dump(mode="json", exclude={"at"}),
                    created_at=stage_record.at,
                )
            ],
        )
