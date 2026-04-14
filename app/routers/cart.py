"""Shopping cart management endpoints.

Provides endpoints for customers to manage their shopping cart:
- View cart items
- Add items to cart
- Update item quantities
- Remove items or clear cart
"""

import uuid
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import require_role
from app.models.cart import CartItem
from app.models.menu_item import MenuItem
from app.models.user import User
from app.schemas.cart import CartItemAdd, CartItemOut, CartItemUpdate
from app.services import get_customer_profile

router = APIRouter(prefix="/cart", tags=["cart"])


async def _enrich_cart_items(
    items: List[CartItem],
    db: AsyncSession,
) -> List[CartItemOut]:
    enriched_items: List[CartItemOut] = []
    for cart_item in items:
        menu_item = await db.get(MenuItem, cart_item.menu_item_id)
        price = Decimal(str(menu_item.price)) if menu_item else Decimal(0)
        enriched_items.append(
            CartItemOut(
                id=cart_item.id,
                menu_item_id=cart_item.menu_item_id,
                quantity=cart_item.quantity,
                name=menu_item.name if menu_item else None,
                unit_price=price,
                subtotal=price * cart_item.quantity,
            )
        )
    return enriched_items


@router.get("", response_model=List[CartItemOut])
async def view_cart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> List[CartItemOut]:
    profile = await get_customer_profile(current_user, db)
    result = await db.scalars(
        select(CartItem).where(CartItem.customer_id == profile.id)
    )
    items = list(result.all())
    return await _enrich_cart_items(items, db)


@router.post("", response_model=CartItemOut, status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    payload: CartItemAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> CartItemOut:
    profile = await get_customer_profile(current_user, db)

    # Validate menu item
    menu_item = await db.get(MenuItem, payload.menu_item_id)
    if not menu_item or not menu_item.is_available:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not available",
        )

    # Check for existing cart item
    existing = await db.scalar(
        select(CartItem).where(
            CartItem.customer_id == profile.id,
            CartItem.menu_item_id == payload.menu_item_id,
        )
    )

    if existing:
        existing.quantity += payload.quantity
        await db.commit()
        await db.refresh(existing)
        cart_item = existing
    else:
        cart_item = CartItem(
            customer_id=profile.id,
            menu_item_id=payload.menu_item_id,
            quantity=payload.quantity,
        )
        db.add(cart_item)
        await db.commit()
        await db.refresh(cart_item)

    price = Decimal(str(menu_item.price))
    return CartItemOut(
        id=cart_item.id,
        menu_item_id=cart_item.menu_item_id,
        quantity=cart_item.quantity,
        name=menu_item.name,
        unit_price=price,
        subtotal=price * cart_item.quantity,
    )


@router.patch("/{item_id}", response_model=CartItemOut)
async def update_cart_item(
    item_id: uuid.UUID,
    payload: CartItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> CartItemOut:
    profile = await get_customer_profile(current_user, db)

    cart_item = await db.get(CartItem, item_id)
    if not cart_item or cart_item.customer_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        )

    cart_item.quantity = payload.quantity
    await db.commit()
    await db.refresh(cart_item)

    menu_item = await db.get(MenuItem, cart_item.menu_item_id)
    price = Decimal(str(menu_item.price)) if menu_item else Decimal(0)

    return CartItemOut(
        id=cart_item.id,
        menu_item_id=cart_item.menu_item_id,
        quantity=cart_item.quantity,
        name=menu_item.name if menu_item else None,
        unit_price=price,
        subtotal=price * cart_item.quantity,
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_cart_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> None:
    profile = await get_customer_profile(current_user, db)

    cart_item = await db.get(CartItem, item_id)
    if not cart_item or cart_item.customer_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        )

    await db.delete(cart_item)
    await db.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> None:
    profile = await get_customer_profile(current_user, db)

    result = await db.scalars(
        select(CartItem).where(CartItem.customer_id == profile.id)
    )
    for cart_item in result.all():
        await db.delete(cart_item)

    await db.commit()
