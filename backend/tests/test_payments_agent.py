import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.errors import GraphRecursionError

from contracts.payments import Verdict
from modules.payments import runner
from modules.payments.agent import (
    PAYMENTS_AGENT_TOOL_NAMES,
    agent_recursion_limit,
    build_payments_agent,
    stream_agent,
)
from modules.payments.agent_state import RunState
from modules.payments.agent_tools import (
    RUN_CHECKER_TOOL,
    SETTLE_DECISION_TOOL,
    STEP_TOOL_NAMES,
    PaymentStepTools,
    next_step_tool,
)
from modules.payments.errors import AgentIncompleteError
from modules.payments.events import DECISION_FAILED_STEP
from modules.payments.limits import AgentLimit, AgentLimitHit, AgentRunLimits, limit_explanation

RUN_LIMITS = AgentRunLimits(run_timeout_s=300, max_tool_calls=30, max_model_calls=35)
RECURSION_LIMIT = agent_recursion_limit(RUN_LIMITS)
ENDLESS_TURNS = 200
ORDERED_STEP_TOOLS = (
    "classify_document",
    "extract_invoice",
    "register_bill",
    "evaluate_rules",
    "run_checker",
    "settle_decision",
)


class ScriptedToolModel(BaseChatModel):
    replies: list[AIMessage]
    visible_tool_names: list[frozenset[str]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _get_ls_params(self, stop: list[str] | None = None, **kwargs: object) -> dict:
        return {"ls_provider": "amazon_bedrock", "ls_model_name": "scripted"}

    def bind_tools(self, tools: list, **kwargs: object) -> "ScriptedToolModel":
        self.visible_tool_names.append(frozenset(_tool_name(tool) for tool in tools))
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        model_turn = len(self.visible_tool_names) - 1
        return ChatResult(generations=[ChatGeneration(message=self.replies[model_turn])])


class RecordingFailClosed:
    def __init__(self) -> None:
        self.failed_bills: list[object] = []
        self.explanations: list[str] = []

    async def __call__(self, dependencies, run_id, bill, policy, explanation) -> None:
        self.failed_bills.append(bill)
        self.explanations.append(explanation)


class FixedLedger:
    def __init__(self, latest_decision: object | None = None) -> None:
        self._latest_decision = latest_decision

    async def latest_decision(self, bill_id: object) -> object | None:
        return self._latest_decision


def _dependencies_with_latest(latest_decision: object | None = None) -> SimpleNamespace:
    return SimpleNamespace(ledger=FixedLedger(latest_decision))


class RecordingEvents:
    def __init__(self) -> None:
        self.steps: list[str] = []

    async def step(self, step: str, payload: dict | None = None) -> None:
        self.steps.append(step)


class RecordingStreamEvents:
    def __init__(self) -> None:
        self.model_calls: list[dict] = []

    async def llm_call(self, **call_fields: object) -> None:
        self.model_calls.append(call_fields)

    async def thinking(self, delta: str) -> None:
        pass

    async def todos(self, todos: list[dict]) -> None:
        pass

    async def tool_started(self, tool: str, call_id: str) -> None:
        pass

    async def tool_finished(
        self, tool: str, call_id: str, output: object, duration_ms: int
    ) -> None:
        pass

    async def agent_summary(self, text: str) -> None:
        pass


async def _classify_with_nested_model() -> str:
    nested_model = GenericFakeChatModel(messages=iter([AIMessage(content="bill")]))
    nested_reply = await nested_model.ainvoke("classify this")
    return json.dumps({"kind": nested_reply.content})


def _tool_name(tool: object) -> str:
    return tool.name if isinstance(tool, BaseTool) else tool["name"]


def _tool_call_reply(tool_name: str, arguments: dict, turn: int) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": tool_name, "args": arguments, "id": f"call-{turn}"}],
    )


def _full_run_script() -> list[AIMessage]:
    todos = [{"content": step, "status": "pending"} for step in ORDERED_STEP_TOOLS]
    replies = [_tool_call_reply("write_todos", {"todos": todos}, 0)]
    for turn, step_tool in enumerate(ORDERED_STEP_TOOLS, start=1):
        replies.append(_tool_call_reply(step_tool, {}, turn * 2 - 1))
        replies.append(_tool_call_reply("write_todos", {"todos": todos}, turn * 2))
    replies.append(AIMessage(content="Factura pagada según las reglas."))
    return replies


def _fake_step_tools() -> list[BaseTool]:
    return [
        StructuredTool.from_function(
            func=lambda: json.dumps({"ok": True}), name=name, description=f"Fake {name}."
        )
        for name in STEP_TOOL_NAMES
    ]


def _run_state(**fields: object) -> RunState:
    return RunState(
        **{"run_id": uuid4(), "owner": object(), "source": object(), "document": object(), **fields}
    )


def _evaluated_state(verdict: Verdict) -> RunState:
    return _run_state(
        classification=object(),
        extraction=object(),
        claim=object(),
        evaluation=SimpleNamespace(verdict=verdict),
    )


async def _invoke(agent, recursion_limit: int) -> None:
    await agent.ainvoke(
        {"messages": [{"role": "user", "content": "process"}]},
        {"recursion_limit": recursion_limit},
    )


async def test_model_sees_only_step_tools_and_write_todos() -> None:
    model = ScriptedToolModel(replies=_full_run_script())
    agent = build_payments_agent(
        model, _fake_step_tools(), "system", checkpointer=None, limits=RUN_LIMITS
    )
    await _invoke(agent, RECURSION_LIMIT)
    assert set(model.visible_tool_names) == {PAYMENTS_AGENT_TOOL_NAMES}


async def test_recursion_limit_fits_a_full_run_with_todo_updates() -> None:
    model = ScriptedToolModel(replies=_full_run_script())
    agent = build_payments_agent(
        model, _fake_step_tools(), "system", checkpointer=None, limits=RUN_LIMITS
    )
    await _invoke(agent, RECURSION_LIMIT)
    tight_model = ScriptedToolModel(replies=_full_run_script())
    tight_agent = build_payments_agent(
        tight_model, _fake_step_tools(), "system", checkpointer=None, limits=RUN_LIMITS
    )
    with pytest.raises(GraphRecursionError):
        await _invoke(tight_agent, RECURSION_LIMIT // 4)


async def test_settle_refuses_to_pay_before_the_checker_runs() -> None:
    state = _evaluated_state(Verdict.PAY)
    step_tools = PaymentStepTools(state, dependencies=None, events=RecordingEvents())
    refusal = json.loads(await step_tools.settle_decision())
    assert refusal["next_tool"] == RUN_CHECKER_TOOL
    assert state.decision is None


async def test_out_of_order_tool_points_to_the_next_step() -> None:
    step_tools = PaymentStepTools(_run_state(), dependencies=None, events=RecordingEvents())
    refusal = json.loads(await step_tools.evaluate_rules())
    assert refusal["next_tool"] == "classify_document"


async def test_checker_is_skipped_when_rules_do_not_allow_paying() -> None:
    held_state = _evaluated_state(Verdict.HOLD)
    step_tools = PaymentStepTools(held_state, dependencies=None, events=RecordingEvents())
    assert json.loads(await step_tools.run_checker())["skipped"] is True
    assert next_step_tool(held_state) == SETTLE_DECISION_TOOL


@pytest.mark.parametrize(
    "settled_fields",
    [{"decision": object()}, {"terminal_reason": "not_a_bill"}],
)
async def test_finalize_is_a_noop_when_the_run_settled(
    settled_fields: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    fail_closed = RecordingFailClosed()
    monkeypatch.setattr(runner, "fail_closed", fail_closed)
    events = RecordingEvents()
    await runner._finalize(_run_state(**settled_fields), None, events)
    assert fail_closed.failed_bills == []
    assert events.steps == []


async def test_finalize_fails_closed_when_a_claimed_bill_is_undecided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fail_closed = RecordingFailClosed()
    monkeypatch.setattr(runner, "fail_closed", fail_closed)
    claimed_bill = SimpleNamespace(bill_id=uuid4())
    events = RecordingEvents()
    claim = SimpleNamespace(bill=claimed_bill, duplicate_of=None)
    await runner._finalize(_run_state(claim=claim), _dependencies_with_latest(), events)
    assert fail_closed.failed_bills == [claimed_bill]
    assert events.steps == [DECISION_FAILED_STEP]


async def test_finalize_raises_when_the_agent_never_claimed_a_bill() -> None:
    with pytest.raises(AgentIncompleteError):
        await runner._finalize(_run_state(), None, RecordingEvents())


async def test_finalize_does_not_fail_closed_an_unsettled_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fail_closed = RecordingFailClosed()
    monkeypatch.setattr(runner, "fail_closed", fail_closed)
    duplicate_claim = SimpleNamespace(bill=object(), duplicate_of=object())
    with pytest.raises(AgentIncompleteError):
        await runner._finalize(_run_state(claim=duplicate_claim), None, RecordingEvents())
    assert fail_closed.failed_bills == []


async def test_step_tools_take_no_input_and_tolerate_parallel_calls() -> None:
    held_state = _evaluated_state(Verdict.HOLD)
    run_checker_tool = next(
        tool
        for tool in PaymentStepTools(held_state, None, RecordingEvents()).as_tools()
        if tool.name == RUN_CHECKER_TOOL
    )
    first_reply, second_reply = await asyncio.gather(
        run_checker_tool.ainvoke({}), run_checker_tool.ainvoke({})
    )
    assert json.loads(first_reply)["skipped"] is True
    assert json.loads(second_reply)["skipped"] is True


async def test_real_step_tools_run_inside_the_agent_graph() -> None:
    held_state = _evaluated_state(Verdict.HOLD)
    step_tools = PaymentStepTools(held_state, dependencies=None, events=RecordingEvents())
    model = ScriptedToolModel(
        replies=[
            _tool_call_reply(RUN_CHECKER_TOOL, {}, 0),
            AIMessage(content="Revisión terminada."),
        ]
    )
    agent = build_payments_agent(
        model, step_tools.as_tools(), "system", checkpointer=None, limits=RUN_LIMITS
    )
    final_state = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "process"}]},
        {"recursion_limit": RECURSION_LIMIT},
    )
    checker_reply = next(
        message
        for message in final_state["messages"]
        if getattr(message, "name", None) == RUN_CHECKER_TOOL
    )
    assert json.loads(checker_reply.content)["skipped"] is True
    assert set(model.visible_tool_names) == {PAYMENTS_AGENT_TOOL_NAMES}


async def test_stream_reports_model_calls_nested_inside_step_tools() -> None:
    classify_tool = StructuredTool.from_function(
        coroutine=_classify_with_nested_model,
        name="classify_document",
        description="Fake classify_document.",
    )
    model = ScriptedToolModel(
        replies=[_tool_call_reply("classify_document", {}, 0), AIMessage(content="Listo.")]
    )
    agent = build_payments_agent(
        model, [classify_tool], "system", checkpointer=None, limits=RUN_LIMITS
    )
    events = RecordingStreamEvents()

    source = SimpleNamespace(
        source_id=uuid4(), source_type="email", sender="billing@acme.test", file_id=None
    )
    await stream_agent(
        agent,
        _run_state(source=source),
        events,
        thinking_flush_seconds=0,
        recursion_limit=RECURSION_LIMIT,
    )

    parent_tools = [call["parent_tool"] for call in events.model_calls]
    assert parent_tools.count(None) == 2
    assert parent_tools.count("classify_document") == 1


@pytest.mark.parametrize(
    ("limits", "expected_error"),
    [
        (
            replace(RUN_LIMITS, max_tool_calls=2),
            ToolCallLimitExceededError,
        ),
        (
            replace(RUN_LIMITS, max_model_calls=3),
            ModelCallLimitExceededError,
        ),
    ],
)
async def test_run_limits_stop_a_run_that_needs_more_calls(
    limits: AgentRunLimits, expected_error: type[Exception]
) -> None:
    model = ScriptedToolModel(replies=_full_run_script())
    agent = build_payments_agent(
        model, _fake_step_tools(), "system", checkpointer=None, limits=limits
    )
    with pytest.raises(expected_error):
        await _invoke(agent, RECURSION_LIMIT)


async def test_limit_hit_maps_only_the_run_deadline_to_a_time_limit() -> None:
    run_deadline = asyncio.timeout(0)
    with pytest.raises(TimeoutError):
        async with run_deadline:
            await asyncio.sleep(1)
    unrelated_deadline = asyncio.timeout(None)
    time_hit = runner._limit_hit(TimeoutError(), run_deadline, RUN_LIMITS)
    assert time_hit == AgentLimitHit(AgentLimit.TIME, RUN_LIMITS.run_timeout_s)
    assert runner._limit_hit(TimeoutError(), unrelated_deadline, RUN_LIMITS) is None
    assert runner._limit_hit(RuntimeError(), unrelated_deadline, RUN_LIMITS) is None


async def test_finalize_escalates_with_the_limit_explanation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fail_closed = RecordingFailClosed()
    monkeypatch.setattr(runner, "fail_closed", fail_closed)
    limit_hit = AgentLimitHit(AgentLimit.TOOL_CALLS, RUN_LIMITS.max_tool_calls)
    claim = SimpleNamespace(bill=SimpleNamespace(bill_id=uuid4()), duplicate_of=None)
    await runner._finalize(
        _run_state(claim=claim, limit_exceeded=limit_hit),
        _dependencies_with_latest(),
        RecordingEvents(),
    )
    assert fail_closed.explanations == [limit_explanation(limit_hit)]


@pytest.mark.parametrize(
    ("limits", "expected_error"),
    [
        (RUN_LIMITS, ToolCallLimitExceededError),
        (
            replace(RUN_LIMITS, max_tool_calls=1000),
            ModelCallLimitExceededError,
        ),
    ],
)
async def test_an_endless_tool_loop_stops_at_a_limit_before_the_recursion_backstop(
    limits: AgentRunLimits, expected_error: type[Exception]
) -> None:
    todos = [{"content": "loop", "status": "pending"}]
    endless_replies = [
        _tool_call_reply("write_todos", {"todos": todos}, turn) for turn in range(ENDLESS_TURNS)
    ]
    model = ScriptedToolModel(replies=endless_replies)
    agent = build_payments_agent(
        model, _fake_step_tools(), "system", checkpointer=None, limits=limits
    )
    with pytest.raises(expected_error):
        await _invoke(agent, agent_recursion_limit(limits))


async def test_finalize_keeps_a_decision_committed_before_the_interruption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fail_closed = RecordingFailClosed()
    monkeypatch.setattr(runner, "fail_closed", fail_closed)
    state = _run_state(
        claim=SimpleNamespace(bill=SimpleNamespace(bill_id=uuid4()), duplicate_of=None)
    )
    committed_decision = SimpleNamespace(run_id=state.run_id)
    events = RecordingEvents()
    await runner._finalize(state, _dependencies_with_latest(committed_decision), events)
    assert fail_closed.failed_bills == []
    assert events.steps == []
