from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

CHECKPOINTER_CONNECTION_OPTIONS = {
    "autocommit": True,
    "prepare_threshold": 0,
    "row_factory": dict_row,
}
CHECKPOINTER_POOL_MIN_SIZE = 1


class Checkpointers:
    def __init__(self, agent_dsn: str, pool_size: int) -> None:
        self._agent_pool = AsyncConnectionPool(
            conninfo=agent_dsn,
            min_size=CHECKPOINTER_POOL_MIN_SIZE,
            max_size=pool_size,
            kwargs=CHECKPOINTER_CONNECTION_OPTIONS,
            open=False,
        )
        self.agent: BaseCheckpointSaver | None = None

    async def open(self) -> None:
        await self._agent_pool.open()
        agent_saver = AsyncPostgresSaver(self._agent_pool)
        await agent_saver.setup()
        self.agent = agent_saver

    async def close(self) -> None:
        await self._agent_pool.close()
