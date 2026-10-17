from typing import Literal
from uuid import UUID

from pydantic import Field

from contracts._base import ApiModel, StrictModel


class ChatRequest(ApiModel):
    message: str = Field(min_length=1)
    session_id: UUID | None = None
    file_ids: list[UUID] = []


class ChatResponse(ApiModel):
    reply: str
    session_id: UUID
    payments_run_id: UUID | None = None


class PreparedChat(StrictModel):
    session_id: UUID
    file_context: str


class ChatStreamEvent(StrictModel):
    type: Literal["token", "tool_started", "payments_scheduled", "done", "error"]
    data: dict = {}
