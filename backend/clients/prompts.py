from typing import TYPE_CHECKING

from pydantic import BaseModel

from contracts.prompts import PromptId

if TYPE_CHECKING:
    from modules.prompts.service import PromptsService


class PromptsClient:
    def __init__(self, service: "PromptsService") -> None:
        self._service = service

    def get_text_prompt(self, prompt_id: PromptId, **variables: object) -> str:
        return self._service.get_text_prompt(prompt_id, **variables)

    def get_response_schema(self, prompt_id: PromptId) -> type[BaseModel]:
        return self._service.get_response_schema(prompt_id)
