from collections.abc import Iterable

from pydantic import BaseModel

from contracts.prompts import PromptId
from modules.prompts.base import Prompt
from modules.prompts.errors import (
    DuplicatePromptIdError,
    MissingPromptsError,
    MissingResponseSchemaError,
)


class PromptsService:
    def __init__(self, prompts: Iterable[Prompt]) -> None:
        self._prompts: dict[PromptId, Prompt] = {}
        for prompt in prompts:
            if prompt.id in self._prompts:
                raise DuplicatePromptIdError(prompt.id)
            self._prompts[prompt.id] = prompt
        unregistered_prompt_ids = set(PromptId) - self._prompts.keys()
        if unregistered_prompt_ids:
            raise MissingPromptsError(sorted(unregistered_prompt_ids))

    def get_text_prompt(self, prompt_id: PromptId, **variables: object) -> str:
        return self._prompts[prompt_id].get_text_prompt(**variables)

    def get_response_schema(self, prompt_id: PromptId) -> type[BaseModel]:
        response_schema = self._prompts[prompt_id].response_schema
        if response_schema is None:
            raise MissingResponseSchemaError(prompt_id)
        return response_schema
