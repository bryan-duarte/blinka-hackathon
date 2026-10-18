# Demo Integrations State Implementation

## Overview

The demo user's Gmail, Outlook and WhatsApp-sandbox connections already persist in `mailbox_connections` (product DB), and demo reset does not delete them. What's missing:
- Freshness: today status is read only from the DB, so a revoked or expired account still shows active.
- A way to verify prod.

This module adds a reconcile-on-read step, a check script, and the operator checklist that leaves prod connected.

**Verified during planning:**
- Local dev has `demo@blinka.dev` with Gmail and Outlook `active` and triggers set. There is no WhatsApp row for the demo user locally.
- Prod is unverified: AWS creds had expired.
- OAuth scopes are out of scope (deferred, see `05-risks.md`).

## Files to Modify/Create

- `backend/modules/inbox/service.py`:
  - `list_connections` (lines 184-189): before returning, call the new `_reconcile_mail_connections(rows)`.
  - Add `self._reconciled_at: dict[UUID, float] = {}` in `__init__`.
- `backend/modules/inbox/repository.py`: reuse `update_connection(connection_id, status)` (already used by `confirm_connection`). Add nothing new unless its signature requires the trigger.
- `backend/clients/mail_gateway.py`: `get_account_status` is already exposed (used by `confirm_connection`). No change.
- `backend/scripts/check_demo_integrations.py` (new): CLI that prints the demo user's integration health. Exit code 0 when healthy, 1 otherwise.

## Implementation Guidelines

```python
# backend/modules/inbox/service.py (orientative)
MAIL_RECONCILE_TTL_SECONDS = 60
RECONCILED_PROVIDERS = frozenset({MailProvider.GMAIL, MailProvider.OUTLOOK})

async def _reconcile_mail_connections(self, connections: list[MailboxConnectionRecord]) -> list[MailboxConnectionRecord]:
    due = [c for c in connections if c.provider in RECONCILED_PROVIDERS
           and c.status is MailAccountStatus.ACTIVE and self._is_reconcile_due(c.connection_id)]
    results = await asyncio.gather(*(self._refresh_status(c) for c in due), return_exceptions=True)
    refreshed = {c.connection_id: r for c, r in zip(due, results) if isinstance(r, MailboxConnectionRecord)}
    return [refreshed.get(c.connection_id, c) for c in connections]

async def _refresh_status(self, connection) -> MailboxConnectionRecord:
    self._reconciled_at[connection.connection_id] = monotonic()
    try:
        status = await self._mail_gateway.get_account_status(connection.connected_account_id)
    except MailProviderError:
        logger.warning("mailbox_reconcile_failed", connection_id=connection.connection_id, exc_info=True)
        return connection
    if status is connection.status:
        return connection
    logger.warning("mailbox_status_changed", connection_id=connection.connection_id, status=status)
    return await self._repository.update_connection(connection.connection_id, status)
```

- Only `active` rows are checked. `initiated` rows are still resolved by the callback page's `confirm`.
- The UI needs no change: `ConnectionBar.tsx:37-48` already shows "Connect Gmail/Outlook" when no `active` row exists.

**`scripts/check_demo_integrations.py`** (follow `scripts/seed_demo.py` for settings and pool bootstrap):
1. Load `Settings()`, build pools, and resolve the demo user by `settings.demo.email`.
2. Print each `mailbox_connections` row for the demo owner: provider, status, mode, phone, `trigger_id`.
3. For Gmail/Outlook rows: print the `connected_accounts.get` status, and whether `trigger_id` is active (`sdk.triggers.list_active(trigger_ids=[...])` or an equivalent in composio 0.28; verify the method name in the installed SDK).
4. Print configured or missing for `COMPOSIO_API_KEY`, both `*_AUTH_CONFIG_ID`, `KAPSO_API_KEY`, `BLINKA_KAPSO__SANDBOX_PHONE_NUMBER_ID` and `BLINKA_KAPSO__SANDBOX_DISPLAY_NUMBER`. Treat `assign_later` and empty values as missing.
5. Healthy means Gmail active with a trigger, Outlook active with a trigger, one active WhatsApp sandbox row, and all settings configured.

Run in prod:

```bash
aws ecs execute-command --profile panoptico --region us-east-1 --cluster <cluster> --task <task> \
  --container backend --interactive --command "uv run --no-sync python -m scripts.check_demo_integrations"
```

**Operator checklist (prod, after modules 01 and 07 are deployed):**
1. Make sure SSM has real values, not `assign_later`, for `COMPOSIO_API_KEY`, `COMPOSIO_WEBHOOK_SECRET`, `BLINKA_COMPOSIO__GMAIL_AUTH_CONFIG_ID`, `BLINKA_COMPOSIO__OUTLOOK_AUTH_CONFIG_ID`, `KAPSO_API_KEY`, `BLINKA_KAPSO__SANDBOX_PHONE_NUMBER_ID` and `BLINKA_KAPSO__SANDBOX_DISPLAY_NUMBER`. `deploy.sh` warns about any that are not.
2. Log in to the prod frontend as `demo@blinka.dev`. Connect Gmail and Outlook through the Connection bar; the callback confirms them.
3. In the WhatsApp dropdown, register your phone in the sandbox and send "join" to the sandbox number, following the Kapso sandbox instructions.
4. Run the check script and expect exit 0.
5. Send a test invoice by email and by WhatsApp, and watch the run in the inbox.

## Dependencies

- Module 01 (lockdown), so only the demo user can change connections.
- Existing `MailGatewayClient.get_account_status` (`modules/mail_gateway/service.py:105-113`).

## Integration Notes

- Contract unchanged: `GET /inbox/connections` → `MailboxConnectionView[]`. The status may now come back `expired` or `failed` after a reconcile.
- Demo reset (`modules/demo/reset_repository.py:54-109`) must keep **not** deleting `mailbox_connections`. Do not change it.
