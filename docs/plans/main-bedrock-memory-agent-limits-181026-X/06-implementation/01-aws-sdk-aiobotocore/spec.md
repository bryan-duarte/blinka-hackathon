# AWS SDK swap: aioboto3 → aiobotocore

## Overview

Replace `aioboto3` with `aiobotocore` 3.x. aioboto3 15.5 pins botocore 1.40.61, which blocks `langchain-aws` ≥1.4 (needs botocore ≥1.43). Behavior is unchanged.

## Files to Modify/Create

- `backend/pyproject.toml` / `uv.lock`: change only through the CLI: `uv remove aioboto3` then `uv add aiobotocore`.
- `backend/modules/document_vision/textract.py`: `TextractExpenseReader.__init__`: session and client context.
- `backend/modules/guardrails/bedrock.py`: `BedrockGuardrailBackend.__init__`: session and `bedrock-runtime` client context.
- `backend/modules/files/storage.py`: `ObjectStorageBackend.__init__`: S3 client context with the existing `Config(s3={"addressing_style": ...})`.
- `backend/modules/realtime/appsync.py`: `_aws_session()` return type and `_signed_headers()` credential retrieval.

## Implementation Guidelines

aioboto3 `Session(profile_name=, region_name=).client(svc)` maps to aiobotocore `AioSession(profile=).create_client(svc, region_name=)`. Both return an async context manager, so the lazy `__aenter__` pattern stays.

```python
# orientative — textract.py
from aiobotocore.session import AioSession

class TextractExpenseReader:
    def __init__(self, aws_profile: str | None, region: str) -> None:
        self._session = AioSession(profile=aws_profile)
        self._client_context = self._session.create_client("textract", region_name=region)
        self._client = None
```

```python
# orientative — storage.py
self._session = AioSession(profile=aws_profile)
self._client_context = self._session.create_client(
    "s3", region_name=region, config=Config(s3={"addressing_style": VIRTUAL_HOST_ADDRESSING})
)
```

```python
# orientative — appsync.py
def _aws_session(self) -> AioSession:
    if self._session is None:
        self._session = AioSession(profile=self._aws_profile)
    return self._session

async def _signed_headers(self, body: bytes) -> dict[str, str]:
    credentials = await self._aws_session().get_credentials()   # async in aiobotocore
    if credentials is None:
        raise RealtimePublishError("no aws credentials")
    frozen_credentials = await credentials.get_frozen_credentials()
    ...
```
- `AioSession(profile=None)` uses the default credential chain (ECS task role), the same as today.
- The AppSync signing region is `self._region`, which is already passed to `SigV4Auth`. No session region is needed.
- Keep `botocore.exceptions` imports as they are. botocore is still the underlying package.
- `grep -rn aioboto3 backend/` must return nothing afterwards, including tests and fakes.

## Dependencies

- `aiobotocore` 3.x (resolves botocore 1.43.x).
- Must be done before module 02's `uv add langchain-aws`.

## Integration Notes

- Constructor signatures of all four adapters are unchanged, so `container.py` needs no edits.
- Close paths: if any adapter has an `aclose`/`__aexit__` on shutdown, it continues to call `self._client_context.__aexit__(None, None, None)` unchanged.
