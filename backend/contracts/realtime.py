from datetime import datetime
from enum import StrEnum
from uuid import UUID

from contracts._base import StrictModel


class RealtimeEventType(StrEnum):
    INBOX_ITEM = "inbox.item"
    PIPELINE_STAGE = "pipeline.stage"
    RUN_STEP = "run.step"
    AGENT_TOOL = "agent.tool"
    AGENT_TODOS = "agent.todos"
    AGENT_THINKING = "agent.thinking"
    AGENT_RULE = "agent.rule"
    AGENT_LLM = "agent.llm"


class RealtimeEvent(StrictModel):
    type: RealtimeEventType
    item_id: UUID | None = None
    run_id: UUID | None = None
    step: str
    payload: dict = {}
    message: str | None = None
    sequence: int | None = None
    created_at: datetime
