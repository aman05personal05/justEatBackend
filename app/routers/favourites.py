import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.dependencies import require_role
from app.models.restaurant import FavouriteRestaurant, Restaurant
from app.models.user import User
from app.schemas.common import AddedToFavouritesResponse
from app.schemas.restaurant import RestaurantOut
from app.services import get_customer_profile

router = APIRouter(prefix="/favourites", tags=["favourites"])


@router.get("", response_model=List[RestaurantOut])
async def list_favourites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> List[Restaurant]:
    profile = await get_customer_profile(current_user, db)

    result = await db.scalars(
        select(FavouriteRestaurant)
        .where(FavouriteRestaurant.customer_id == profile.id)
        .options(selectinload(FavouriteRestaurant.restaurant))
    )
    return [fav.restaurant for fav in result.all()]


@router.post(
    "/{restaurant_id}",
    response_model=AddedToFavouritesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_favourite(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> AddedToFavouritesResponse:
    profile = await get_customer_profile(current_user, db)

    # Validate restaurant exists
    restaurant = await db.get(Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found",
        )

    # Check if already favourited
    existing = await db.scalar(
        select(FavouriteRestaurant).where(
            FavouriteRestaurant.customer_id == profile.id,
            FavouriteRestaurant.restaurant_id == restaurant_id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already in favourites",
        )

    db.add(
        FavouriteRestaurant(
            customer_id=profile.id,
            restaurant_id=restaurant_id,
        )
    )
    await db.commit()

    return AddedToFavouritesResponse(detail="Added to favourites")


@router.delete("/{restaurant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favourite(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> None:
    profile = await get_customer_profile(current_user, db)

    favourite = await db.scalar(
        select(FavouriteRestaurant).where(
            FavouriteRestaurant.customer_id == profile.id,
            FavouriteRestaurant.restaurant_id == restaurant_id,
        )
    )
    if not favourite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not in favourites",
        )

    await db.delete(favourite)
    await db.commit()
