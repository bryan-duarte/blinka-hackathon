from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.base import BaseStore
from langgraph.store.postgres import AsyncPostgresStore
from langgraph.store.postgres.base import PostgresIndexConfig
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

CHECKPOINTER_CONNECTION_OPTIONS = {
    "autocommit": True,
    "prepare_threshold": 0,
    "row_factory": dict_row,
}
CHECKPOINTER_POOL_MIN_SIZE = 1


class Checkpointers:
    def __init__(
        self, agent_dsn: str, pool_size: int, store_index: PostgresIndexConfig | None = None
    ) -> None:
        self._store_index = store_index
        self._agent_pool = AsyncConnectionPool(
            conninfo=agent_dsn,
            min_size=CHECKPOINTER_POOL_MIN_SIZE,
            max_size=pool_size,
            kwargs=CHECKPOINTER_CONNECTION_OPTIONS,
            open=False,
        )
        self.agent: BaseCheckpointSaver | None = None
        self.store: BaseStore | None = None

    async def open(self) -> None:
        await self._agent_pool.open()
        agent_saver = AsyncPostgresSaver(self._agent_pool)
        await agent_saver.setup()
        self.agent = agent_saver
        if self._store_index is not None:
            self.store = await self._open_store(self._store_index)

    async def _open_store(self, store_index: PostgresIndexConfig) -> BaseStore:
        agent_store = AsyncPostgresStore(self._agent_pool, index=store_index)
        await agent_store.setup()
        return agent_store

    async def close(self) -> None:
        await self._agent_pool.close()
