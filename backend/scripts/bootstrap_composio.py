import sys

from composio import Composio
from composio.exceptions import ComposioError
from composio_client import APIError

from core.config import ComposioSettings

TOOLKIT_ENV_KEYS = {
    "gmail": "BLINKA_COMPOSIO__GMAIL_AUTH_CONFIG_ID",
    "outlook": "BLINKA_COMPOSIO__OUTLOOK_AUTH_CONFIG_ID",
}
MANAGED_AUTH_TYPE = "use_composio_managed_auth"
LISTENER_INSTRUCTIONS = """
Dev listener (export the same secret in this shell and in backend/.env):
  export COMPOSIO_WEBHOOK_SECRET=$(openssl rand -hex 32)
  composio dev triggers listen --forward http://localhost:8000/webhooks/mail
"""


def main() -> int:
    settings = ComposioSettings()
    try:
        composio = Composio(api_key=settings.api_key.get_secret_value())
        auth_config_ids = {
            toolkit: _managed_auth_config_id(composio, toolkit) for toolkit in TOOLKIT_ENV_KEYS
        }
    except (ComposioError, APIError) as error:
        print(f"Composio error: {error}", file=sys.stderr)
        return 1
    for toolkit, auth_config_id in auth_config_ids.items():
        print(f"{TOOLKIT_ENV_KEYS[toolkit]}={auth_config_id}")
    print(LISTENER_INSTRUCTIONS)
    return 0


def _managed_auth_config_id(composio: Composio, toolkit: str) -> str:
    existing_configs = composio.auth_configs.list(toolkit_slug=toolkit, is_composio_managed=True)
    if existing_configs.items:
        return existing_configs.items[0].id
    created_config = composio.auth_configs.create(
        toolkit=toolkit, options={"type": MANAGED_AUTH_TYPE, "name": f"Blinka {toolkit}"}
    )
    return created_config.id


if __name__ == "__main__":
    sys.exit(main())
