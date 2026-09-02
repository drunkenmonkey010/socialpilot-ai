from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.brand import BrandCreate, BrandResponse, BrandUpdate
from app.services.brand import BrandService


router = APIRouter(
    prefix="/brands",
    tags=["Brands"],
)


@router.post(
    "",
    response_model=BrandResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_brand(
    data: BrandCreate,
    session: AsyncSession = Depends(get_db),
):
    service = BrandService(session)
    return await service.create_brand(data)


@router.get(
    "/{brand_id}",
    response_model=BrandResponse,
)
async def get_brand(
    brand_id: int,
    session: AsyncSession = Depends(get_db),
):
    service = BrandService(session)

    brand = await service.get_brand(brand_id)

    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    return brand


@router.get(
    "/user/{user_id}",
    response_model=list[BrandResponse],
)
async def get_user_brands(
    user_id: int,
    session: AsyncSession = Depends(get_db),
):
    service = BrandService(session)
    return await service.get_user_brands(user_id)


@router.patch(
    "/{brand_id}",
    response_model=BrandResponse,
)
async def update_brand(
    brand_id: int,
    data: BrandUpdate,
    session: AsyncSession = Depends(get_db),
):
    service = BrandService(session)

    brand = await service.update_brand(brand_id, data)

    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    return brand


@router.delete(
    "/{brand_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_brand(
    brand_id: int,
    session: AsyncSession = Depends(get_db),
):
    service = BrandService(session)

    deleted = await service.delete_brand(brand_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )