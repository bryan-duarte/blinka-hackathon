from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from contracts.prompts import PromptId


class Prompt(ABC):
    id: ClassVar[PromptId]
    response_schema: ClassVar[type[BaseModel] | None] = None

    @abstractmethod
    def get_text_prompt(self, **variables: object) -> str: ...
