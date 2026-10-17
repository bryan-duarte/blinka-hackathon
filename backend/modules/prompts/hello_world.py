from contracts.prompts import HelloWorldReport, PromptId
from modules.prompts.base import Prompt

HELLO_WORLD_TASK = """This is Blinka's pipeline check.
1. Call the `get_system_profile` tool exactly once.
2. Call the `get_random_token` tool exactly once.
3. Respond with a short greeting and copy the exact `token` and `generated_at` values
   returned by `get_random_token`, the `name` returned by `get_system_profile`, and the
   names of the tools you called. Never invent values; only report what the tools returned."""


class HelloWorldPrompt(Prompt):
    id = PromptId.HELLO_WORLD
    response_schema = HelloWorldReport

    def get_text_prompt(self) -> str:
        return HELLO_WORLD_TASK
