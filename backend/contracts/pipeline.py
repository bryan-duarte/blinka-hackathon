from datetime import datetime
from enum import StrEnum
from typing import Literal

from contracts._base import ApiModel

PipelineStageStatus = Literal["started", "finished", "failed"]


class PipelineStage(StrEnum):
    QUEUED = "queued"
    FETCH = "fetch"
    MALWARE_SCAN = "malware_scan"
    GUARDRAIL = "guardrail"
    DEDUP = "dedup"
    HANDOFF = "handoff"


class PipelineStageRecord(ApiModel):
    stage: PipelineStage
    status: PipelineStageStatus
    duration_ms: int | None = None
    detail: dict = {}
    at: datetime
