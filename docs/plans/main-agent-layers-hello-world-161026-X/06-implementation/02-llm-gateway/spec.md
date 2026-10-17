# LLM Gateway Implementation

## Overview

Replace `ChatOpenAI` with `BearerAuthChatAnthropic`, which points at OpenRouter's Anthropic-compatible endpoint, as in the reference repo. Use a single default Haiku model with optional per-kind overrides, and build the model instances once.

## Files to Modify/Create

All paths are under `backend/`.

- `core/config.py`: in `LlmSettings`, replace the fields with the set in `03-design.md` (`base_url`, `api_key`, `model`, `main_model | None`, `payments_model | None`, `max_tokens`, `timeout_s`, `max_retries`). The prefix stays `BLINKA_LLM__`.
- `modules/llm_gateway/service.py`:
  - add `BearerAuthChatAnthropic`;
  - rewrite `__init__`, `model()` and `_model_name()`;
  - add `default_model()`;
  - remove the `langchain_openai` import;
  - leave `extract()` and `_extract_via_json_mode()` untouched.
- `clients/llm.py`: add `default_model() -> "BaseChatModel"`.
- `pyproject.toml`: add `"langchain-anthropic>=1.7,<1.8"` and remove `"langchain-openai>=1.0"`, then run `uv lock && uv sync`.
- `.env.example`: replace the LLM block with the following.
  ```
  OPENROUTER_API_KEY=
  BLINKA_LLM__MODEL=anthropic/claude-haiku-5.5
  # BLINKA_LLM__MAIN_MODEL=
  # BLINKA_LLM__PAYMENTS_MODEL=
  ```
  Note: `.env.example` already uses `#` comment lines, so these are consistent with the file.

## Implementation Guidelines

The snippets below are orientative.

```python
class BearerAuthChatAnthropic(ChatAnthropic):
    _bearer_token: SecretStr = PrivateAttr()

    def __init__(self, *, bearer_token: SecretStr, model: str, base_url: str,
                 max_tokens: int, timeout_s: float, max_retries: int) -> None:
        super().__init__(api_key=bearer_token, model=model, base_url=base_url,
                         max_tokens=max_tokens, timeout=timeout_s, max_retries=max_retries,
                         temperature=DETERMINISTIC_TEMPERATURE)
        self._bearer_token = bearer_token

    @cached_property
    def _client_params(self) -> dict[str, Any]:
        client_params = super()._client_params
        client_params["default_headers"] = {
            **client_params["default_headers"],
            "Authorization": f"Bearer {self._bearer_token.get_secret_value()}",
        }
        return client_params


class LlmGatewayService:
    def __init__(self, settings: LlmSettings) -> None:
        self._settings = settings
        model_names = {settings.model, *self._override_names()}
        self._chat_models: dict[str, BaseChatModel] = {
            model_name: self._build_chat_model(model_name) for model_name in model_names
        }

    def default_model(self) -> BaseChatModel:
        return self._chat_models[self._settings.model]

    def model(self, kind: ModelKind) -> BaseChatModel:
        if kind not in MODEL_KINDS:
            raise ModelNotConfiguredError
        return self._chat_models[self._model_name(kind)]

    def _model_name(self, kind: ModelKind) -> str:
        override = self._settings.main_model if kind == "main" else self._settings.payments_model
        return override or self._settings.model
```

- `_override_names()` returns the non-`None` values among `main_model` and `payments_model`. Inline it if that reads better.
- Check that the `super()._client_params` call works on a `cached_property`. The reference does exactly this with langchain-anthropic 1.7.5. In 1.7.6, `_client_params` is a `@cached_property` at `chat_models.py:1739`.
- Leave the `extract()` body as is. `with_structured_output` works with ChatAnthropic.
- `MODEL_KINDS`, `DETERMINISTIC_TEMPERATURE` and `JSON_MODE_ATTEMPTS` stay.

## Dependencies

- `langchain-anthropic` 1.7.6 (`langchain_anthropic.ChatAnthropic`)
- `pydantic.PrivateAttr`, `pydantic.SecretStr`
- `functools.cached_property`

## Integration Notes

- `LlmGatewayClient.model(kind)` keeps its signature, so the orchestrator chat, payments runner and invoice ingestor need no change for the LLM switch itself.
- Module 04 uses `LlmGatewayClient.default_model()`.
- Base URL: `https://openrouter.ai/api`, without `/v1`. Anthropic's SDK appends `/v1/messages`.
