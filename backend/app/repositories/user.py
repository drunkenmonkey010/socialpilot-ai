from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Repository for database operations on users."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        """Return a user by primary key."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Return a user by email address."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        password_hash: str,
    ) -> User:
        """Create and persist a new user."""
        user = User(
            email=email,
            password_hash=password_hash,
        )

        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)

        return user

    async def update(
        self,
        user: User,
        **updates: object,
    ) -> User:
        """Update fields on an existing user."""
        for field, value in updates.items():
            if hasattr(user, field):
                setattr(user, field, value)

        await self.session.flush()
        await self.session.refresh(user)

        return user

    async def delete(self, user: User) -> None:
        """Delete an existing user."""
        await self.session.delete(user)
        await self.session.flush()