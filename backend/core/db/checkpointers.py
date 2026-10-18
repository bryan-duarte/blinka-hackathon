from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


class Checkpointers:
    def __init__(self, payments_dsn: str) -> None:
        self._payments_connection = AsyncPostgresSaver.from_conn_string(payments_dsn)
        self.payments: BaseCheckpointSaver | None = None

    async def open(self) -> None:
        payments_saver = await self._payments_connection.__aenter__()
        await payments_saver.setup()
        self.payments = payments_saver

    async def close(self) -> None:
        await self._payments_connection.__aexit__(None, None, None)
