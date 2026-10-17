from typing import Literal

from modules.prompts.main_agent import MAIN_AGENT_PROMPT
from modules.prompts.payment_agent import PAYMENT_AGENT_PROMPT

PromptName = Literal["main_agent", "payment_agent"]

_PROMPTS = {
    "main_agent": MAIN_AGENT_PROMPT,
    "payment_agent": PAYMENT_AGENT_PROMPT,
}


def get_prompt(name: PromptName) -> str:
    return _PROMPTS[name]


__all__ = ["MAIN_AGENT_PROMPT", "PAYMENT_AGENT_PROMPT", "PromptName", "get_prompt"]
