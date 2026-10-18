import asyncio
import sys

from core.config import KapsoSettings
from modules.whatsapp_gateway import WhatsAppGatewayService, WhatsAppProviderError

WEBHOOK_URL_INSTRUCTIONS = """
Kapso needs a public https URL for the webhook. In local dev:
  ngrok http 8000
  BLINKA_KAPSO__WEBHOOK_URL=https://<id>.ngrok.app/webhooks/whatsapp
  KAPSO_WEBHOOK_SECRET=$(openssl rand -hex 32)
Then run this script again to register the sandbox webhook.
"""
SANDBOX_DISPLAY_NUMBER_HINT = (
    "BLINKA_KAPSO__SANDBOX_DISPLAY_NUMBER=<copy it from Kapso → WhatsApp → Sandbox>"
)


async def bootstrap(settings: KapsoSettings) -> int:
    gateway = WhatsAppGatewayService(settings)
    phone_numbers = await gateway.list_phone_numbers()
    sandbox_number = next((number for number in phone_numbers if number.is_sandbox), None)
    if sandbox_number is None:
        print("No Kapso sandbox number found in this project.", file=sys.stderr)
        return 1
    print(f"BLINKA_KAPSO__SANDBOX_PHONE_NUMBER_ID={sandbox_number.phone_number_id}")
    print(SANDBOX_DISPLAY_NUMBER_HINT)
    has_webhook_config = bool(settings.webhook_url) and bool(
        settings.webhook_secret.get_secret_value()
    )
    if not has_webhook_config:
        print(WEBHOOK_URL_INSTRUCTIONS)
        return 0
    registered_urls = await gateway.list_message_webhook_urls(sandbox_number.phone_number_id)
    if settings.webhook_url in registered_urls:
        print(f"Sandbox webhook already registered: {settings.webhook_url}")
        return 0
    webhook_id = await gateway.register_message_webhook(sandbox_number.phone_number_id)
    print(f"Sandbox webhook registered ({webhook_id}): {settings.webhook_url}")
    return 0


def main() -> int:
    try:
        return asyncio.run(bootstrap(KapsoSettings()))
    except WhatsAppProviderError as error:
        print(f"Kapso error: {error!r}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
