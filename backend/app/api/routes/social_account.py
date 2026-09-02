from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.social_account import (
    SocialAccountCreate,
    SocialAccountResponse,
    SocialAccountUpdate,
)
from app.services.social_account import SocialAccountService


router = APIRouter(
    prefix="/social-accounts",
    tags=["Social Accounts"],
)


@router.post(
    "",
    response_model=SocialAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_social_account(
    data: SocialAccountCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await SocialAccountService.create_account(
        session,
        current_user.id,
        data,
    )


@router.get(
    "",
    response_model=list[SocialAccountResponse],
)
async def get_my_social_accounts(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await SocialAccountService.get_user_accounts(
        session,
        current_user.id,
    )


@router.get(
    "/{account_id}",
    response_model=SocialAccountResponse,
)
async def get_social_account(
    account_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = await SocialAccountService.get_account(
        session,
        account_id,
        current_user.id,
    )

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social account not found",
        )

    return account


@router.patch(
    "/{account_id}",
    response_model=SocialAccountResponse,
)
async def update_social_account(
    account_id: int,
    data: SocialAccountUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = await SocialAccountService.get_account(
        session,
        account_id,
        current_user.id,
    )

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social account not found",
        )

    return await SocialAccountService.update_account(
        session,
        account,
        data,
    )


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_social_account(
    account_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = await SocialAccountService.get_account(
        session,
        account_id,
        current_user.id,
    )

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social account not found",
        )

    await SocialAccountService.delete_account(
        session,
        account,
    )