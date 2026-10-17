from collections.abc import Iterator
from typing import Protocol

from contracts.guardrails import GuardrailCheckRequest, GuardrailVerdict
from core.config import GuardrailsSettings
from core.logging_config import get_logger
from modules.guardrails.errors import GuardrailRejectionError

logger = get_logger(__name__)

GUARD_CHUNK_CHARS = 25_000
GUARD_CHUNK_OVERLAP_CHARS = 500


class GuardrailBackend(Protocol):
    async def apply(self, text: str) -> GuardrailVerdict: ...


class GuardrailsService:
    def __init__(self, settings: GuardrailsSettings, backend: GuardrailBackend) -> None:
        self._enforce = settings.enforce
        self._backend = backend

    async def check(self, request: GuardrailCheckRequest) -> GuardrailVerdict:
        if not self._enforce:
            return GuardrailVerdict(allowed=True, violations=[])
        for chunk in _chunks(request.context, GUARD_CHUNK_CHARS, GUARD_CHUNK_OVERLAP_CHARS):
            verdict = await self._backend.apply(chunk)
            if not verdict.allowed:
                violation_codes = [violation.code for violation in verdict.violations]
                logger.info("guardrail_blocked", codes=violation_codes)
                return verdict
        logger.debug("guardrail_checked", context_chars=len(request.context))
        return GuardrailVerdict(allowed=True, violations=[])

    async def require_allowed(self, request: GuardrailCheckRequest) -> None:
        verdict = await self.check(request)
        if not verdict.allowed:
            raise GuardrailRejectionError(verdict)


def _chunks(text: str, chunk_chars: int, overlap_chars: int) -> Iterator[str]:
    stride = chunk_chars - overlap_chars
    for start in range(0, len(text), stride):
        chunk_end = start + chunk_chars
        yield text[start:chunk_end]
        if chunk_end >= len(text):
            return
