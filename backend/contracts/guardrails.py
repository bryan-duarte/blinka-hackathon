from contracts._base import StrictModel


class GuardrailCheckRequest(StrictModel):
    context: str


class GuardrailViolation(StrictModel):
    code: str
    message: str


class GuardrailVerdict(StrictModel):
    allowed: bool
    violations: list[GuardrailViolation] = []
