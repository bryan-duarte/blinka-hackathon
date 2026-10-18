from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

ASYNC_DRIVER_SCHEME = "postgresql+psycopg://"


def to_async_dsn(dsn: str) -> str:
    if dsn.startswith(ASYNC_DRIVER_SCHEME):
        return dsn
    return ASYNC_DRIVER_SCHEME + dsn.removeprefix("postgresql://")


def create_engine_and_sessionmaker(
    dsn: str, pool_size: int, max_overflow: int
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        to_async_dsn(dsn), pool_size=pool_size, max_overflow=max_overflow, pool_pre_ping=True
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@dataclass(frozen=True)
class DatabasePool:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]


@dataclass(frozen=True)
class Pools:
    product: DatabasePool
    agent: DatabasePool


def build_pools(product_dsn: str, agent_dsn: str, pool_size: int, max_overflow: int) -> Pools:
    return Pools(
        product=DatabasePool(*create_engine_and_sessionmaker(product_dsn, pool_size, max_overflow)),
        agent=DatabasePool(*create_engine_and_sessionmaker(agent_dsn, pool_size, max_overflow)),
    )
