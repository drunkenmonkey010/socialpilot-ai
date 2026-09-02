from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social_account import SocialAccount
from app.repositories.social_account import SocialAccountRepository
from app.schemas.social_account import (
    SocialAccountCreate,
    SocialAccountUpdate,
)


class SocialAccountService:
    """Business operations for SocialAccount entities."""

    @staticmethod
    async def create_account(
        db: AsyncSession,
        user_id: int,
        account_data: SocialAccountCreate,
    ) -> SocialAccount:
        social_account = SocialAccount(
            user_id=user_id,
            platform=account_data.platform,
            account_name=account_data.account_name,
            account_id=account_data.account_id,
            access_token=account_data.access_token,
            refresh_token=account_data.refresh_token,
            token_expires_at=account_data.token_expires_at,
            is_active=account_data.is_active,
        )

        return await SocialAccountRepository.create(
            db,
            social_account,
        )

    @staticmethod
    async def get_account(
        db: AsyncSession,
        account_id: int,
        user_id: int,
    ) -> SocialAccount | None:
        return await SocialAccountRepository.get_by_id_for_user(
            db,
            account_id,
            user_id,
        )

    @staticmethod
    async def get_user_accounts(
        db: AsyncSession,
        user_id: int,
    ) -> list[SocialAccount]:
        return await SocialAccountRepository.get_by_user_id(
            db,
            user_id,
        )

    @staticmethod
    async def update_account(
        db: AsyncSession,
        account: SocialAccount,
        account_data: SocialAccountUpdate,
    ) -> SocialAccount:
        update_data = account_data.model_dump(
            exclude_unset=True,
        )

        for field, value in update_data.items():
            setattr(account, field, value)

        return await SocialAccountRepository.update(
            db,
            account,
        )

    @staticmethod
    async def delete_account(
        db: AsyncSession,
        account: SocialAccount,
    ) -> None:
        await SocialAccountRepository.delete(
            db,
            account,
        )