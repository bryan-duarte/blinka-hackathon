from collections.abc import Iterable

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError

from contracts.guardrails import GuardrailVerdict, GuardrailViolation
from modules.guardrails.errors import GuardrailUnavailableError

GUARD_SOURCE = "INPUT"
GUARD_QUALIFIERS = ["guard_content"]
BLOCKED_ACTION = "BLOCKED"
SENSITIVE_INFORMATION_MESSAGE = "sensitive information blocked"

Assessment = dict


class BedrockGuardrailBackend:
    def __init__(
        self,
        guardrail_id: str,
        guardrail_version: str,
        aws_profile: str | None,
        aws_region: str,
    ) -> None:
        self._guardrail_id = guardrail_id
        self._guardrail_version = guardrail_version
        self._session = aioboto3.Session(profile_name=aws_profile, region_name=aws_region)
        self._client_context = self._session.client("bedrock-runtime")
        self._client = None

    async def _runtime_client(self):
        if self._client is None:
            self._client = await self._client_context.__aenter__()
        return self._client

    async def apply(self, text: str) -> GuardrailVerdict:
        try:
            client = await self._runtime_client()
            response = await client.apply_guardrail(
                guardrailIdentifier=self._guardrail_id,
                guardrailVersion=self._guardrail_version,
                source=GUARD_SOURCE,
                content=[{"text": {"text": text, "qualifiers": GUARD_QUALIFIERS}}],
            )
        except (ClientError, BotoCoreError) as error:
            raise GuardrailUnavailableError from error
        violations = _blocked_violations(response.get("assessments", []))
        return GuardrailVerdict(allowed=not violations, violations=violations)


def _blocked_violations(assessments: list[Assessment]) -> list[GuardrailViolation]:
    violations_by_code: dict[str, GuardrailViolation] = {}
    for assessment in assessments:
        for violation in _assessment_violations(assessment):
            violations_by_code.setdefault(violation.code, violation)
    return list(violations_by_code.values())


def _assessment_violations(assessment: Assessment) -> Iterable[GuardrailViolation]:
    content_policy = assessment.get("contentPolicy", {})
    topic_policy = assessment.get("topicPolicy", {})
    word_policy = assessment.get("wordPolicy", {})
    sensitive_policy = assessment.get("sensitiveInformationPolicy", {})
    for content_filter in _blocked(content_policy.get("filters", [])):
        filter_type = content_filter["type"]
        yield GuardrailViolation(
            code=f"content.{filter_type.lower()}",
            message=f"{filter_type} detected with {content_filter.get('confidence')} confidence",
        )
    for topic in _blocked(topic_policy.get("topics", [])):
        yield GuardrailViolation(
            code=f"topic.{topic['name']}", message=f"denied topic {topic['name']}"
        )
    for custom_word in _blocked(word_policy.get("customWords", [])):
        yield GuardrailViolation(code="word.custom", message=custom_word["match"])
    for managed_word in _blocked(word_policy.get("managedWordLists", [])):
        yield GuardrailViolation(code="word.managed", message=managed_word["match"])
    for pii_entity in _blocked(sensitive_policy.get("piiEntities", [])):
        yield GuardrailViolation(
            code=f"pii.{pii_entity['type'].lower()}", message=SENSITIVE_INFORMATION_MESSAGE
        )
    for regex in _blocked(sensitive_policy.get("regexes", [])):
        yield GuardrailViolation(
            code=f"regex.{regex['name']}", message=SENSITIVE_INFORMATION_MESSAGE
        )


def _blocked(findings: list[Assessment]) -> list[Assessment]:
    return [finding for finding in findings if finding.get("action") == BLOCKED_ACTION]
