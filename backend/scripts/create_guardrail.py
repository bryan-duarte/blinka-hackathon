import argparse
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_PROFILE = "panoptico"
DEFAULT_REGION = "us-east-1"
DEFAULT_NAME = "blinka-email-input-guard"
STANDARD_TIER = "STANDARD"
CROSS_REGION_PROFILE = "us.guardrail.v1:0"
ACCESS_DENIED_CODE = "AccessDeniedException"
REQUIRED_IAM_ACTIONS = (
    "bedrock:CreateGuardrail",
    "bedrock:CreateGuardrailVersion",
    "bedrock:ListGuardrails",
    "bedrock:ApplyGuardrail",
)
MODERATED_CONTENT_TYPES = ("HATE", "INSULTS", "SEXUAL", "VIOLENCE", "MISCONDUCT")
BLOCKED_MESSAGE = "Este correo fue bloqueado por las políticas de seguridad. / Blocked by policy."
VERSION_DESCRIPTION = "email input guard"


def main() -> int:
    arguments = _parse_arguments()
    session = boto3.Session(profile_name=arguments.profile, region_name=arguments.region)
    bedrock = session.client("bedrock")
    try:
        guardrail_id = _existing_guardrail_id(bedrock, arguments.name)
        if guardrail_id is None:
            guardrail_id = _create_guardrail(bedrock, arguments.name)
        version = bedrock.create_guardrail_version(
            guardrailIdentifier=guardrail_id, description=VERSION_DESCRIPTION
        )["version"]
    except ClientError as error:
        _report_client_error(error)
        return 1
    except BotoCoreError as error:
        print(f"AWS error: {error}", file=sys.stderr)
        return 1
    print(f"BLINKA_GUARDRAILS__GUARDRAIL_ID={guardrail_id}")
    print(f"BLINKA_GUARDRAILS__GUARDRAIL_VERSION={version}")
    return 0


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the Blinka email input guardrail.")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--name", default=DEFAULT_NAME)
    return parser.parse_args()


def _existing_guardrail_id(bedrock, name: str) -> str | None:
    for page in bedrock.get_paginator("list_guardrails").paginate():
        for guardrail in page["guardrails"]:
            if guardrail["name"] == name:
                return guardrail["id"]
    return None


def _create_guardrail(bedrock, name: str) -> str:
    response = bedrock.create_guardrail(
        name=name,
        description="Screens untrusted email text before any Blinka agent reads it.",
        contentPolicyConfig={
            "filtersConfig": [
                _prompt_attack_filter(),
                *map(_moderation_filter, MODERATED_CONTENT_TYPES),
            ],
            "tierConfig": {"tierName": STANDARD_TIER},
        },
        crossRegionConfig={"guardrailProfileIdentifier": CROSS_REGION_PROFILE},
        blockedInputMessaging=BLOCKED_MESSAGE,
        blockedOutputsMessaging=BLOCKED_MESSAGE,
    )
    return response["guardrailId"]


def _prompt_attack_filter() -> dict:
    return {
        "type": "PROMPT_ATTACK",
        "inputStrength": "HIGH",
        "outputStrength": "NONE",
        "inputAction": "BLOCK",
        "inputEnabled": True,
    }


def _moderation_filter(content_type: str) -> dict:
    return {"type": content_type, "inputStrength": "MEDIUM", "outputStrength": "NONE"}


def _report_client_error(error: ClientError) -> None:
    error_details = error.response.get("Error", {})
    error_code = error_details.get("Code")
    print(f"{error_code}: {error_details.get('Message')}", file=sys.stderr)
    if error_code == ACCESS_DENIED_CODE:
        print("Grant these IAM actions: " + ", ".join(REQUIRED_IAM_ACTIONS), file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
