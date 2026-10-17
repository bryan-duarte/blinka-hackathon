from datetime import datetime
from uuid import UUID

from contracts._base import ApiModel, StrictModel


class SessionCreated(StrictModel):
    session_id: UUID


class SessionSummary(ApiModel):
    session_id: UUID
    title: str
    updated_at: datetime


class ExecutionRecorded(StrictModel):
    execution_id: UUID


class ExecutionRecord(StrictModel):
    execution_id: UUID
    session_id: UUID
    agent: str
    input_summary: str
    output_summary: str
    occurred_at: datetime
