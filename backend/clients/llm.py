from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from contracts.llm import ModelKind
from core.agents import MessageContent

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

    from modules.llm_gateway.service import LlmGatewayService

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LlmGatewayClient:
    def __init__(self, service: "LlmGatewayService") -> None:
        self._service = service

    def default_model(self) -> "BaseChatModel":
        return self._service.default_model()

    def model(self, kind: ModelKind) -> "BaseChatModel":
        return self._service.model(kind)

    async def extract(
        self,
        model_kind: ModelKind,
        system: str,
        user_content: MessageContent,
        schema: type[SchemaT],
    ) -> SchemaT:
        return await self._service.extract(model_kind, system, user_content, schema)
