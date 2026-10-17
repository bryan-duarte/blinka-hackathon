from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.auth import UserCredentials
from modules.auth.errors import EmailTakenError
from modules.auth.models import User


class UsersRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def insert(self, email: str, password_hash: str) -> UUID:
        user = User(email=email, password_hash=password_hash)
        async with self._sessionmaker() as session:
            session.add(user)
            try:
                await session.commit()
            except IntegrityError as error:
                raise EmailTakenError from error
            return user.id

    async def get_by_email(self, email: str) -> UserCredentials | None:
        async with self._sessionmaker() as session:
            result = await session.execute(select(User).where(User.email == email))
            return _to_credentials(result.scalar_one_or_none())

    async def get_by_id(self, user_id: UUID) -> UserCredentials | None:
        async with self._sessionmaker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return _to_credentials(result.scalar_one_or_none())


def _to_credentials(user: User | None) -> UserCredentials | None:
    if user is None:
        return None
    return UserCredentials(user_id=user.id, email=user.email, password_hash=user.password_hash)
