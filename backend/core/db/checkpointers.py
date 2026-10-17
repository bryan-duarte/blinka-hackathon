from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


class Checkpointers:
    def __init__(self, agent_dsn: str, payments_dsn: str) -> None:
        self._agent_connection = AsyncPostgresSaver.from_conn_string(agent_dsn)
        self._payments_connection = AsyncPostgresSaver.from_conn_string(payments_dsn)
        self.agent: BaseCheckpointSaver | None = None
        self.payments: BaseCheckpointSaver | None = None

    async def open(self) -> None:
        agent_saver = await self._agent_connection.__aenter__()
        payments_saver = await self._payments_connection.__aenter__()
        await agent_saver.setup()
        await payments_saver.setup()
        self.agent = agent_saver
        self.payments = payments_saver

    async def close(self) -> None:
        await self._payments_connection.__aexit__(None, None, None)
        await self._agent_connection.__aexit__(None, None, None)
