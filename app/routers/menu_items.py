import uuid
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.dependencies import require_role
from app.models.menu_item import MenuItem
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.menu_item import MenuItemCreate, MenuItemOut, MenuItemUpdate

router = APIRouter(prefix="/restaurants/{restaurant_id}/menu-items", tags=["menu-items"])


async def _get_restaurant_or_404(restaurant_id: uuid.UUID, db: AsyncSession) -> Restaurant:
    r = await db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    return r


async def _get_item_or_404(item_id: uuid.UUID, restaurant_id: uuid.UUID, db: AsyncSession) -> MenuItem:
    item = await db.get(MenuItem, item_id)
    if not item or item.restaurant_id != restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    return item


@router.get("", response_model=List[MenuItemOut])
async def list_menu_items(
    restaurant_id: uuid.UUID,
    category: Optional[str] = None,
    is_special: Optional[bool] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(MenuItem).where(MenuItem.restaurant_id == restaurant_id)
    if category:
        q = q.where(MenuItem.category == category)
    if is_special is not None:
        q = q.where(MenuItem.is_special == is_special)
    if min_price is not None:
        q = q.where(MenuItem.price >= min_price)
    if max_price is not None:
        q = q.where(MenuItem.price <= max_price)
    return (await db.scalars(q.order_by(MenuItem.category, MenuItem.name))).all()


@router.get("/mostly-ordered", response_model=List[MenuItemOut])
async def get_mostly_ordered(restaurant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    q = (
        select(MenuItem)
        .where(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.order_count >= settings.MOSTLY_ORDERED_THRESHOLD,
            MenuItem.is_available.is_(True),
        )
        .order_by(desc(MenuItem.order_count))
    )
    return (await db.scalars(q)).all()


@router.get("/{item_id}", response_model=MenuItemOut)
async def get_menu_item(restaurant_id: uuid.UUID, item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _get_item_or_404(item_id, restaurant_id, db)


@router.post("", response_model=MenuItemOut, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
    restaurant_id: uuid.UUID,
    payload: MenuItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    r = await _get_restaurant_or_404(restaurant_id, db)
    if r.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    item = MenuItem(**payload.model_dump(), restaurant_id=restaurant_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=MenuItemOut)
async def update_menu_item(
    restaurant_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: MenuItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    r = await _get_restaurant_or_404(restaurant_id, db)
    if r.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    item = await _get_item_or_404(item_id, restaurant_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu_item(
    restaurant_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    r = await _get_restaurant_or_404(restaurant_id, db)
    if r.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    item = await _get_item_or_404(item_id, restaurant_id, db)
    await db.delete(item)
    await db.commit()


@router.post("/{item_id}/toggle-special", response_model=MenuItemOut)
async def toggle_special(
    restaurant_id: uuid.UUID, item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    r = await _get_restaurant_or_404(restaurant_id, db)
    if r.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    item = await _get_item_or_404(item_id, restaurant_id, db)
    item.is_special = not item.is_special
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/{item_id}/toggle-available", response_model=MenuItemOut)
async def toggle_available(
    restaurant_id: uuid.UUID, item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    r = await _get_restaurant_or_404(restaurant_id, db)
    if r.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    item = await _get_item_or_404(item_id, restaurant_id, db)
    item.is_available = not item.is_available
    await db.commit()
    await db.refresh(item)
    return item
