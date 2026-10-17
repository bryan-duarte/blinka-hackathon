from contracts.guardrails import GuardrailVerdict


class GuardrailsError(Exception):
    pass


class GuardrailRejectionError(GuardrailsError):
    def __init__(self, verdict: GuardrailVerdict) -> None:
        super().__init__("guardrail rejection")
        self.verdict = verdict


class GuardrailUnavailableError(GuardrailsError):
    pass
