"""Print the demo account's intake health: mailboxes, triggers and the WhatsApp sandbox.

Run (from backend/): uv run python -m scripts.check_demo_integrations
Exits 0 when Gmail and Outlook are active with a trigger, one WhatsApp sandbox phone is
active, and every integration setting is configured; exits 1 otherwise.
"""

import asyncio
import sys

from contracts.inbox import MailboxConnectionRecord
from contracts.mail_gateway import MailAccountStatus, MailProvider
from contracts.whatsapp_gateway import WhatsAppConnectionMode
from core.config import Settings
from core.db import create_engine_and_sessionmaker
from modules.auth import UsersRepository
from modules.inbox import InboxRepository
from modules.mail_gateway import MailGatewayService, MailProviderError

UNASSIGNED_SETTING_VALUE = "assign_later"
SCRIPT_POOL_SIZE = 1
SCRIPT_MAX_OVERFLOW = 0
TRIGGERED_PROVIDERS = (MailProvider.GMAIL, MailProvider.OUTLOOK)


async def check_demo_integrations() -> int:
    settings = Settings()
    engine, sessionmaker = create_engine_and_sessionmaker(
        settings.product_database_url, SCRIPT_POOL_SIZE, SCRIPT_MAX_OVERFLOW
    )
    try:
        demo_user = await UsersRepository(sessionmaker).get_by_email(settings.demo.email.lower())
        if demo_user is None:
            print(f"Demo account {settings.demo.email} does not exist.")
            return 1
        connections = await InboxRepository(sessionmaker).list_connections(demo_user.user_id)
    finally:
        await engine.dispose()
    _print_connections(connections)
    has_mailboxes = await _check_mailboxes(MailGatewayService(settings.composio), connections)
    has_sandbox_phone = _check_sandbox(connections)
    has_settings = _check_settings(settings)
    is_healthy = has_mailboxes and has_sandbox_phone and has_settings
    print(f"\nHEALTHY: {'yes' if is_healthy else 'no'}")
    return 0 if is_healthy else 1


def _print_connections(connections: list[MailboxConnectionRecord]) -> None:
    print("Connections for the demo account:")
    for connection in connections:
        print(
            f"  {connection.provider:<9} status={connection.status:<9} "
            f"mode={connection.mode or '-':<10} phone={connection.phone_number or '-':<16} "
            f"trigger={connection.trigger_id or '-'}"
        )


async def _check_mailboxes(
    mail_gateway: MailGatewayService, connections: list[MailboxConnectionRecord]
) -> bool:
    print("\nMailboxes (live provider status):")
    try:
        active_trigger_ids = await mail_gateway.active_trigger_ids(
            [connection.trigger_id for connection in connections if connection.trigger_id]
        )
    except MailProviderError:
        print("  could not list triggers: mail provider unavailable")
        return False
    healthy_providers = set()
    for connection in connections:
        if connection.provider not in TRIGGERED_PROVIDERS:
            continue
        is_healthy = await _check_mailbox(mail_gateway, connection, active_trigger_ids)
        if is_healthy:
            healthy_providers.add(connection.provider)
    for provider in TRIGGERED_PROVIDERS:
        print(f"  {provider}: {'ok' if provider in healthy_providers else 'MISSING'}")
    return healthy_providers == set(TRIGGERED_PROVIDERS)


async def _check_mailbox(
    mail_gateway: MailGatewayService,
    connection: MailboxConnectionRecord,
    active_trigger_ids: set[str],
) -> bool:
    try:
        live_status = await mail_gateway.get_account_status(connection.connected_account_id)
    except MailProviderError:
        print(f"  {connection.connected_account_id}: provider unavailable")
        return False
    has_active_trigger = connection.trigger_id in active_trigger_ids
    print(
        f"  {connection.provider} {connection.connected_account_id}: live={live_status} "
        f"trigger_active={'yes' if has_active_trigger else 'no'}"
    )
    return live_status is MailAccountStatus.ACTIVE and has_active_trigger


def _check_sandbox(connections: list[MailboxConnectionRecord]) -> bool:
    active_sandbox_phones = [
        connection.phone_number
        for connection in connections
        if connection.mode is WhatsAppConnectionMode.SANDBOX
        and connection.status is MailAccountStatus.ACTIVE
    ]
    print(f"\nWhatsApp sandbox phones (active): {active_sandbox_phones or 'none'}")
    return len(active_sandbox_phones) == 1


def _check_settings(settings: Settings) -> bool:
    integration_settings = {
        "COMPOSIO_API_KEY": settings.composio.api_key.get_secret_value(),
        "BLINKA_COMPOSIO__GMAIL_AUTH_CONFIG_ID": settings.composio.gmail_auth_config_id,
        "BLINKA_COMPOSIO__OUTLOOK_AUTH_CONFIG_ID": settings.composio.outlook_auth_config_id,
        "KAPSO_API_KEY": settings.kapso.api_key.get_secret_value(),
        "BLINKA_KAPSO__SANDBOX_PHONE_NUMBER_ID": settings.kapso.sandbox_phone_number_id,
        "BLINKA_KAPSO__SANDBOX_DISPLAY_NUMBER": settings.kapso.sandbox_display_number,
    }
    print("\nSettings:")
    missing_settings = [
        name
        for name, setting_value in integration_settings.items()
        if setting_value in ("", UNASSIGNED_SETTING_VALUE)
    ]
    for name in integration_settings:
        print(f"  {name}: {'MISSING' if name in missing_settings else 'configured'}")
    return not missing_settings


def main() -> None:
    sys.exit(asyncio.run(check_demo_integrations()))


if __name__ == "__main__":
    main()
