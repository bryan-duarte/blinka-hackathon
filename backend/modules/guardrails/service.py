from contracts.guardrails import GuardrailCheckRequest, GuardrailVerdict
from core.logging_config import get_logger
from modules.guardrails.errors import GuardrailRejectionError

logger = get_logger(__name__)


class GuardrailsService:
    def __init__(self, enforce: bool) -> None:
        self._enforce = enforce

    async def check(self, request: GuardrailCheckRequest) -> GuardrailVerdict:
        logger.debug(
            "guardrail_checked",
            enforce=self._enforce,
            context_chars=len(request.context),
        )
        return GuardrailVerdict(allowed=True, violations=[])

    async def require_allowed(self, request: GuardrailCheckRequest) -> None:
        verdict = await self.check(request)
        if not verdict.allowed:
            raise GuardrailRejectionError(verdict)
