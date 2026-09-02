from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import create_access_token
from app.core.security import verify_password
from app.models.user import User
from app.repositories.user import UserRepository


class AuthService:
    """Service layer for authentication."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = UserRepository(session)

    async def authenticate(
        self,
        email: str,
        password: str,
    ) -> User | None:
        """Authenticate a user using email and password."""
        user = await self.repository.get_by_email(email)

        if user is None:
            return None

        if not user.is_active:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user

    def create_token(self, user: User) -> str:
        """Create an access token for an authenticated user."""
        return create_access_token(str(user.id))