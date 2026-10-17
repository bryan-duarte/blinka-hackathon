from typing import TYPE_CHECKING

from contracts.guardrails import GuardrailCheckRequest, GuardrailVerdict

if TYPE_CHECKING:
    from modules.guardrails.service import GuardrailsService


class GuardrailsClient:
    def __init__(self, service: "GuardrailsService") -> None:
        self._service = service

    async def check(self, request: GuardrailCheckRequest) -> GuardrailVerdict:
        return await self._service.check(request)

    async def require_allowed(self, request: GuardrailCheckRequest) -> None:
        await self._service.require_allowed(request)
