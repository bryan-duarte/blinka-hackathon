import json
from collections.abc import Sequence
from datetime import UTC, datetime
from time import monotonic
from typing import TYPE_CHECKING
from uuid import UUID

from langchain_core.messages import ToolMessage

from contracts.payments import PaymentRunEvent, RuleEffect, RuleResult, Verdict
from contracts.realtime import RealtimeEvent, RealtimeEventType
from core.agents import message_text
from modules.payments.phrases import pick_step_phrase, pick_tool_error_phrase, pick_tool_phrase
from modules.payments.repository import RunsRepository

if TYPE_CHECKING:
    from clients.realtime import RealtimeClient

STARTED_STEP = "started"
CLASSIFIED_STEP = "classified"
NOT_A_BILL_STEP = "not_a_bill"
EXTRACTED_STEP = "extracted"
EXTRACTION_FAILED_STEP = "extraction_failed"
CLAIMED_STEP = "claimed"
DECIDED_STEP = "decided"
DECISION_FAILED_STEP = "decision_failed"
COMPLETED_STEP = "completed"
CANCELLED_STEP = "cancelled"
FAILED_STEP = "failed"
TOOL_STARTED_STEP = "tool_started"
TOOL_FINISHED_STEP = "tool_finished"
TODOS_UPDATED_STEP = "todos_updated"
AGENT_SUMMARY_STEP = "agent_summary"
THINKING_STEP = "thinking"
FX_CONVERTED_STEP = "fx_converted"
RULE_EVALUATED_STEP = "rule_evaluated"
RULES_EVALUATED_STEP = "rules_evaluated"
CHECKER_ANSWERED_STEP = "checker_answered"
LLM_CALL_STEP = "llm_call"
LIMIT_EXCEEDED_STEP = "limit_exceeded"
PRECEDENTS_RECALLED_STEP = "precedents_recalled"
TOOL_SUMMARY_MAX_CHARS = 1000
AGENT_SUMMARY_MAX_CHARS = 2000
RULE_EVIDENCE_MAX_CHARS = 1000
REALTIME_PAYLOAD_MAX_BYTES = 16_000
REALTIME_TRUNCATED_STRING_CHARS = 1000
REALTIME_BULKY_KEYS = frozenset({"evidence", "summary", "fields", "todos", "answers"})
TOOL_ERROR_STATUS = "error"
TOOL_ERROR_KEY = "error"


class RunEventRecorder:
    def __init__(
        self,
        repository: RunsRepository,
        realtime: "RealtimeClient",
        owner_id: UUID,
        run_id: UUID,
    ) -> None:
        self._repository = repository
        self._realtime = realtime
        self._owner_id = owner_id
        self._run_id = run_id
        self._item_id: UUID | None = None

    def bind_item(self, item_id: UUID | None) -> None:
        self._item_id = item_id

    async def step(
        self, step: str, payload: dict | None = None, realtime_payload: dict | None = None
    ) -> None:
        message = pick_step_phrase(step)
        message_field = {"message": message} if message else {}
        step_payload = {**(payload or {}), **message_field}
        stored_event = await self._repository.insert_event(self._run_id, step, step_payload)
        published_payload = (
            step_payload if realtime_payload is None else {**realtime_payload, **message_field}
        )
        await self._publish(RealtimeEventType.RUN_STEP, stored_event, message, published_payload)

    async def rules(self, results: Sequence[RuleResult], provisional_verdict: Verdict) -> None:
        flagged_count = sum(1 for result in results if result.effect is not RuleEffect.PASS)
        summary_payload = {
            "provisional_verdict": provisional_verdict,
            "passed_count": len(results) - flagged_count,
            "flagged_count": flagged_count,
        }
        rule_events = [(RULE_EVALUATED_STEP, _rule_payload(result)) for result in results]
        stored_events = await self._repository.insert_events(
            self._run_id, [*rule_events, (RULES_EVALUATED_STEP, summary_payload)]
        )
        await self._realtime.publish(
            self._owner_id,
            [
                self._realtime_event(_rule_event_type(stored_event), stored_event, None)
                for stored_event in stored_events
            ],
        )

    async def llm_call(
        self,
        node: str,
        parent_tool: str | None,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
    ) -> None:
        stored_event = await self._repository.insert_event(
            self._run_id,
            LLM_CALL_STEP,
            {
                "node": node,
                "parent_tool": parent_tool,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "duration_ms": duration_ms,
            },
        )
        await self._publish(RealtimeEventType.AGENT_LLM, stored_event, None)

    async def tool_started(self, tool: str, call_id: str) -> None:
        message = pick_tool_phrase(tool, "start")
        stored_event = await self._repository.insert_event(
            self._run_id, TOOL_STARTED_STEP, {"tool": tool, "call_id": call_id, "message": message}
        )
        await self._publish(RealtimeEventType.AGENT_TOOL, stored_event, message)

    async def tool_finished(
        self, tool: str, call_id: str, output: object, duration_ms: int
    ) -> None:
        summary = _tool_output_text(output)
        is_ok = _tool_succeeded(output, summary)
        message = pick_tool_phrase(tool, "finish") if is_ok else pick_tool_error_phrase()
        stored_event = await self._repository.insert_event(
            self._run_id,
            TOOL_FINISHED_STEP,
            {
                "tool": tool,
                "call_id": call_id,
                "tool_call_id": output.tool_call_id if isinstance(output, ToolMessage) else None,
                "message": message,
                "ok": is_ok,
                "duration_ms": duration_ms,
                "summary": summary[:TOOL_SUMMARY_MAX_CHARS],
            },
        )
        await self._publish(RealtimeEventType.AGENT_TOOL, stored_event, message)

    async def todos(self, todos: list[dict]) -> None:
        stored_event = await self._repository.insert_event(
            self._run_id, TODOS_UPDATED_STEP, {"todos": todos}
        )
        await self._publish(RealtimeEventType.AGENT_TODOS, stored_event, None)

    async def agent_summary(self, text: str) -> None:
        stored_event = await self._repository.insert_event(
            self._run_id, AGENT_SUMMARY_STEP, {"text": text[:AGENT_SUMMARY_MAX_CHARS]}
        )
        await self._publish(RealtimeEventType.RUN_STEP, stored_event, None)

    async def thinking(self, delta: str) -> None:
        await self._realtime.publish(
            self._owner_id,
            [
                RealtimeEvent(
                    type=RealtimeEventType.AGENT_THINKING,
                    item_id=self._item_id,
                    run_id=self._run_id,
                    step=THINKING_STEP,
                    payload={"text": delta},
                    created_at=datetime.now(UTC),
                )
            ],
        )

    async def _publish(
        self,
        event_type: RealtimeEventType,
        stored_event: PaymentRunEvent,
        message: str | None,
        realtime_payload: dict | None = None,
    ) -> None:
        await self._realtime.publish(
            self._owner_id,
            [self._realtime_event(event_type, stored_event, message, realtime_payload)],
        )

    def _realtime_event(
        self,
        event_type: RealtimeEventType,
        stored_event: PaymentRunEvent,
        message: str | None,
        realtime_payload: dict | None = None,
    ) -> RealtimeEvent:
        return RealtimeEvent(
            type=event_type,
            item_id=self._item_id,
            run_id=self._run_id,
            step=stored_event.step,
            payload=_cap_payload(
                stored_event.payload if realtime_payload is None else realtime_payload
            ),
            message=message,
            sequence=stored_event.id,
            created_at=stored_event.created_at,
        )


class ThinkingBuffer:
    def __init__(self, recorder: RunEventRecorder, flush_interval_seconds: float) -> None:
        self._recorder = recorder
        self._flush_interval_seconds = flush_interval_seconds
        self._pending_text = ""
        self._last_flush_at = monotonic()

    async def add(self, text: str) -> None:
        self._pending_text += text
        is_flush_due = monotonic() - self._last_flush_at >= self._flush_interval_seconds
        if is_flush_due:
            await self.flush()

    async def flush(self) -> None:
        self._last_flush_at = monotonic()
        if not self._pending_text:
            return
        pending_text, self._pending_text = self._pending_text, ""
        await self._recorder.thinking(pending_text)


def _cap_payload(payload: dict) -> dict:
    encoded_size = len(json.dumps(payload, default=str).encode())
    if encoded_size <= REALTIME_PAYLOAD_MAX_BYTES:
        return payload
    slim_payload = {
        key: value[:REALTIME_TRUNCATED_STRING_CHARS] if isinstance(value, str) else value
        for key, value in payload.items()
        if key not in REALTIME_BULKY_KEYS
    }
    return {**slim_payload, "truncated": True}


def _rule_payload(result: RuleResult) -> dict:
    return {
        "code": result.rule_id,
        "name": result.name,
        "outcome": result.effect,
        "detail": result.reason,
        "evidence": _trimmed_evidence(result.evidence),
    }


def _trimmed_evidence(evidence: dict[str, str]) -> dict[str, str]:
    is_within_limit = len(json.dumps(evidence)) <= RULE_EVIDENCE_MAX_CHARS
    if is_within_limit:
        return evidence
    per_value_chars = RULE_EVIDENCE_MAX_CHARS // max(len(evidence), 1)
    return {key: value[:per_value_chars] for key, value in evidence.items()}


def _rule_event_type(stored_event: PaymentRunEvent) -> RealtimeEventType:
    if stored_event.step == RULE_EVALUATED_STEP:
        return RealtimeEventType.AGENT_RULE
    return RealtimeEventType.RUN_STEP


def _tool_output_text(output: object) -> str:
    if isinstance(output, ToolMessage):
        return message_text(output.content)
    return str(output)


def _tool_succeeded(output: object, output_text: str) -> bool:
    is_error_message = isinstance(output, ToolMessage) and output.status == TOOL_ERROR_STATUS
    if is_error_message:
        return False
    try:
        parsed_output = json.loads(output_text)
    except json.JSONDecodeError:
        return True
    return not (isinstance(parsed_output, dict) and TOOL_ERROR_KEY in parsed_output)
