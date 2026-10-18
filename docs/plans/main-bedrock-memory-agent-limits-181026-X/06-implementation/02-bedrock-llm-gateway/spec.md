# Bedrock LLM Gateway

## Overview

Swap `ChatAnthropic` over OpenRouter for `ChatBedrockConverse`, using Claude Haiku 5.5 for every model kind. Remove OpenRouter completely, and keep deepagents' tool exclusions working under the new provider key.

## Files to Modify/Create

- `backend/pyproject.toml` / `uv.lock`: `uv add langchain-aws langmem`. Then `uv remove langchain-anthropic` if `grep -rn langchain_anthropic backend/ --include='*.py'` is empty after the gateway edit. `langmem` is added here so a single resolve happens; it is used in module 05.
- `backend/core/config.py`:
  - `LlmSettings`: remove `base_url` and `api_key`.
  - Add `aws_profile: str | None = None`, `aws_region: str = "us-east-1"`, `connect_timeout_s: float = 5`.
  - Default `model = "global.anthropic.claude-haiku-5-5"`.
- `backend/modules/llm_gateway/service.py`: `_build_chat_model`; build the botocore `Config` once in `__init__`.
- `backend/modules/invoice_ingestor/service.py`:
  - `_build_pdf_content` (`:236-247`): sanitize `filename`.
  - Add a module-level helper `_converse_document_name(filename: str | None) -> str`.
- `backend/modules/payments/agent.py`:
  - Replace `PAYMENTS_MODEL_PROVIDER = "anthropic"` with `PAYMENTS_MODEL_PROVIDERS = ("anthropic", "amazon_bedrock")`.
  - Register the profile in a loop.
- `backend/core/agents.py`: `message_text`. Ensure only `{"type": "text"}` blocks (and plain strings) are concatenated, and `reasoning`/`reasoning_content`/`thinking` blocks are skipped.
- `backend/modules/llm_gateway/service.py` `_extract_via_json_mode`: `response.text` already ignores non-text blocks in langchain-core 1.6. Keep it as is.
- `backend/.env.example`:
  - Remove `OPENROUTER_API_KEY`.
  - Set `BLINKA_LLM__MODEL=global.anthropic.claude-haiku-5-5`.
  - Add `BLINKA_LLM__AWS_PROFILE=panoptico`, `BLINKA_LLM__AWS_REGION=us-east-1`.
- `backend/tests/test_payments_agent.py:52`: the fake model's `ls_provider` becomes `"amazon_bedrock"`, so the tool-set assertion covers the new registration. Minimal edit to keep the existing tests meaningful; no new tests.

## Implementation Guidelines

```python
# orientative — llm_gateway/service.py
from botocore.config import Config
from langchain_aws import ChatBedrockConverse

ADAPTIVE_RETRY_MODE = "adaptive"

class LlmGatewayService:
    def __init__(self, settings: LlmSettings) -> None:
        self._settings = settings
        self._client_config = Config(
            connect_timeout=settings.connect_timeout_s,
            read_timeout=settings.timeout_s,
            retries={"max_attempts": settings.max_retries + 1, "mode": ADAPTIVE_RETRY_MODE},
        )
        ...  # unchanged model-name dedup

    def _build_chat_model(self, model_name: str) -> BaseChatModel:
        return ChatBedrockConverse(
            model=model_name,
            region_name=self._settings.aws_region,
            credentials_profile_name=self._settings.aws_profile,
            max_tokens=self._settings.max_tokens,
            temperature=DETERMINISTIC_TEMPERATURE,
            config=self._client_config,
        )
```

```python
# orientative — invoice_ingestor/service.py
CONVERSE_DOCUMENT_NAME_MAX = 200
CONVERSE_DOCUMENT_NAME_DISALLOWED = re.compile(r"[^A-Za-z0-9\-\(\)\[\] ]+")
DEFAULT_DOCUMENT_NAME = "invoice"

def _converse_document_name(filename: str | None) -> str:
    stem = (filename or "").rsplit(".", 1)[0]
    cleaned = " ".join(CONVERSE_DOCUMENT_NAME_DISALLOWED.sub("-", stem).split())
    return cleaned[:CONVERSE_DOCUMENT_NAME_MAX] or DEFAULT_DOCUMENT_NAME
```
- The Converse `DocumentBlock.name` allows only alphanumerics, single spaces, `-`, `()` and `[]`. Dots are rejected.

```python
# orientative — payments/agent.py
PAYMENTS_MODEL_PROVIDERS = ("anthropic", "amazon_bedrock")
for model_provider in PAYMENTS_MODEL_PROVIDERS:
    register_harness_profile(model_provider, PAYMENTS_HARNESS_PROFILE)
```
- Keep `"anthropic"` so the existing fake-model tests and any local fallback still match. deepagents matches the provider key exactly against `ls_provider`.
- deepagents auto-adds `BedrockPromptCachingMiddleware` when `langchain_aws.middleware` imports (langchain-aws ≥1.4). No code is needed. Confirm that the `agent.llm` events show `cache_read` tokens after deploy, if usage metadata exposes them.
- `with_structured_output(schema)` on ChatBedrockConverse uses forced tool calling. The existing JSON-mode fallback in `extract()` stays as the safety net.
- Model-name overrides: `main_model` and `payments_model` stay optional. With all three unset except `model`, a single `ChatBedrockConverse` instance is built.

## Dependencies

- Module 01 must land first; otherwise uv resolves langchain-aws 1.1.0.
- `langchain-aws` (target ≥1.9), `langmem` 0.0.30.

## Integration Notes

- The `LlmGatewayClient` API (`default_model`, `model(kind)`, `extract`) is unchanged.
- `metadata["ls_model_name"]` in `agent.py:_record_model_call` now reports the profile ID (`global.anthropic.claude-haiku-5-5`). The frontend LLM stats show it verbatim.
- Module 05 builds `BedrockEmbeddings` with the same profile and region pattern, from `MemorySettings`.
