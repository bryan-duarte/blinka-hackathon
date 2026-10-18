from dataclasses import dataclass
from enum import StrEnum


class AgentLimit(StrEnum):
    TIME = "time"
    TOOL_CALLS = "tool_calls"
    MODEL_CALLS = "model_calls"


@dataclass(frozen=True)
class AgentRunLimits:
    run_timeout_s: float
    max_tool_calls: int
    max_model_calls: int


@dataclass(frozen=True)
class AgentLimitHit:
    limit: AgentLimit
    threshold: float | int


LIMIT_EXCEEDED_REASON_PREFIX = "limit_exceeded:"
LIMIT_UNITS = {
    AgentLimit.TIME: "seconds",
    AgentLimit.TOOL_CALLS: "tool calls",
    AgentLimit.MODEL_CALLS: "model calls",
}


def limit_failure_reason(hit: AgentLimitHit) -> str:
    return f"{LIMIT_EXCEEDED_REASON_PREFIX}{hit.limit}"


def limit_explanation(hit: AgentLimitHit) -> str:
    return (
        f"In review: the agent stopped at its safety limit of {hit.threshold:g} "
        f"{LIMIT_UNITS[hit.limit]} before finishing its checks. A person needs to review "
        "this invoice."
    )
