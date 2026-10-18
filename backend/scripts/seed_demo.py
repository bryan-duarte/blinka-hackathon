"""Create and seed the demo account, or reset it to its initial state.

Run (from backend/): uv run python -m scripts.seed_demo [--reset]
"""

import argparse
import asyncio
import sys

from container import build_clients
from core.config import Settings
from core.db import Checkpointers, build_pools
from core.logging_config import configure_logging


async def seed_demo(is_reset: bool) -> int:
    settings = Settings()
    configure_logging(settings.log_format)
    if not settings.demo.enabled:
        print("Demo mode is disabled: set BLINKA_DEMO__ENABLED=true.", file=sys.stderr)
        return 1
    workers = settings.workers
    pools = build_pools(
        settings.product_database_url,
        settings.agent_database_url,
        workers.db_pool_size,
        workers.db_max_overflow,
    )
    checkpointers = Checkpointers(settings.agent_database_url, workers.checkpointer_pool_size)
    await checkpointers.open()
    try:
        clients = await build_clients(settings, pools, checkpointers)
        owner = await clients.demo.ensure_demo_account()
        if is_reset:
            reset_result = await clients.demo.reset(owner)
            print(
                f"Demo reset: {reset_result.seeded_bills} historical bills loaded for {owner.email}"
            )
        else:
            print(f"Demo account ready: {owner.email}")
        return 0
    finally:
        await checkpointers.close()
        await pools.product.engine.dispose()
        await pools.agent.engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="wipe and re-seed the demo account")
    arguments = parser.parse_args()
    sys.exit(asyncio.run(seed_demo(arguments.reset)))


if __name__ == "__main__":
    main()
