from typing import TypeVar, get_args

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from contracts.llm import ModelKind
from core.agents import MessageContent
from core.config import LlmSettings
from core.logging_config import get_logger
from modules.llm_gateway.errors import ModelNotConfiguredError, StructuredExtractionError

SchemaT = TypeVar("SchemaT", bound=BaseModel)

MODEL_KINDS = get_args(ModelKind)
DETERMINISTIC_TEMPERATURE = 0
JSON_MODE_ATTEMPTS = 2

logger = get_logger(__name__)


class LlmGatewayService:
    def __init__(self, settings: LlmSettings) -> None:
        self._settings = settings
        configured_model_names = {
            model_name
            for model_name in (settings.model, settings.main_model, settings.payments_model)
            if model_name
        }
        self._chat_models: dict[str, BaseChatModel] = {
            model_name: self._build_chat_model(model_name) for model_name in configured_model_names
        }

    def default_model(self) -> BaseChatModel:
        return self._chat_models[self._settings.model]

    def model(self, kind: ModelKind) -> BaseChatModel:
        if kind not in MODEL_KINDS:
            raise ModelNotConfiguredError
        return self._chat_models[self._model_name(kind)]

    async def extract(
        self,
        model_kind: ModelKind,
        system: str,
        user_content: MessageContent,
        schema: type[SchemaT],
    ) -> SchemaT:
        model = self.model(model_kind)
        messages: list[BaseMessage] = [
            SystemMessage(content=system),
            HumanMessage(content=user_content),
        ]
        try:
            structured_model = model.with_structured_output(schema)
            extracted = await structured_model.ainvoke(messages)
        except Exception as provider_error:
            logger.warning(
                "structured_output_fallback_to_json_mode",
                model_kind=model_kind,
                error=str(provider_error),
            )
            return await self._extract_via_json_mode(model, messages, schema)
        if not isinstance(extracted, schema):
            raise StructuredExtractionError
        return extracted

    async def _extract_via_json_mode(
        self,
        model: BaseChatModel,
        messages: list[BaseMessage],
        schema: type[SchemaT],
    ) -> SchemaT:
        json_system = f"{messages[0].content}\nRespond with ONLY the raw JSON object."
        json_messages = [SystemMessage(content=json_system), *messages[1:]]
        for _ in range(JSON_MODE_ATTEMPTS):
            response = await model.ainvoke(json_messages)
            try:
                return schema.model_validate_json(response.text)
            except ValidationError as validation_error:
                json_messages = [
                    *json_messages,
                    response,
                    HumanMessage(content=f"Invalid JSON or schema: {validation_error}. Try again."),
                ]
        raise StructuredExtractionError

    def _model_name(self, kind: ModelKind) -> str:
        override_model_name = (
            self._settings.main_model if kind == "main" else self._settings.payments_model
        )
        return override_model_name or self._settings.model

    def _build_chat_model(self, model_name: str) -> BaseChatModel:
        return ChatAnthropic(
            model=model_name,
            base_url=self._settings.base_url,
            api_key=self._settings.api_key,
            max_tokens=self._settings.max_tokens,
            timeout=self._settings.timeout_s,
            max_retries=self._settings.max_retries,
            temperature=DETERMINISTIC_TEMPERATURE,
        )
