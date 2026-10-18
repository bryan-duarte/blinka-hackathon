from datetime import UTC, datetime
from typing import TYPE_CHECKING

from contracts.auth import CurrentUser
from core.logging_config import get_logger
from modules.demo.seed_data import (
    DEMO_BLACKLIST,
    DEMO_PAYEES,
    DEMO_POLICY,
    DEMO_TRUSTED_FORWARDERS,
    history,
)
from modules.demo.seed_repository import DemoSeedRepository

if TYPE_CHECKING:
    from clients.payment_policy import PaymentPolicyClient

logger = get_logger(__name__)


class DemoSeeder:
    def __init__(self, policy: "PaymentPolicyClient", seed_repository: DemoSeedRepository) -> None:
        self._policy = policy
        self._seed_repository = seed_repository

    async def seed(self, owner: CurrentUser) -> int:
        await self._policy.update_policy(owner, DEMO_POLICY)
        payees_by_name = {}
        for payee in DEMO_PAYEES:
            created = await self._policy.create_payee(owner, payee)
            payees_by_name[created.display_name] = created
        for entry in DEMO_BLACKLIST:
            await self._policy.add_blacklist_entry(owner, entry)
        for forwarder in DEMO_TRUSTED_FORWARDERS:
            await self._policy.add_trusted_forwarder(owner, forwarder)
        policy = await self._policy.get_policy(owner)
        seeded_bills = await self._seed_repository.insert_history(
            owner.user_id, policy, payees_by_name, history(datetime.now(UTC).date())
        )
        logger.info("demo_seeded", owner_id=owner.user_id, seeded_bills=seeded_bills)
        return seeded_bills
