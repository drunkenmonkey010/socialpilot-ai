from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate


class UserService:
    """Service layer for user business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = UserRepository(session)

    async def get_by_id(self, user_id: int) -> User | None:
        """Return a user by ID."""
        return await self.repository.get_by_id(user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Return a user by email."""
        return await self.repository.get_by_email(email)

    async def create(self, data: UserCreate) -> User:
        """Create a new user with a securely hashed password."""
        existing_user = await self.repository.get_by_email(str(data.email))

        if existing_user is not None:
            raise ValueError("A user with this email already exists")

        password_hash = hash_password(data.password)

        return await self.repository.create(
            email=str(data.email),
            password_hash=password_hash,
        )