from datetime import datetime
from enum import StrEnum
from uuid import UUID

from contracts._base import ApiModel, StrictModel


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PaymentRunRecord(StrictModel):
    run_id: UUID
    status: RunStatus
    error: str | None = None


class PaymentRunTrigger(ApiModel):
    file_id: UUID
    session_id: UUID | None = None


class PaymentRunAccepted(ApiModel):
    run_id: UUID
    status: RunStatus


class PaymentRunEvent(StrictModel):
    step: str
    payload: dict = {}
    created_at: datetime


class PaymentRunStatus(ApiModel):
    run_id: UUID
    status: RunStatus
    error: str | None = None
    events: list[PaymentRunEvent] = []
