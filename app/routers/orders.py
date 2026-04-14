import uuid
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.models.menu_item import MenuItem
from app.models.order import ORDER_STATUS_TRANSITIONS, Order, OrderItem, OrderStatus
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.order import OrderOut, OrderPlace, OrderStatusUpdate
from app.services import get_customer_profile

router = APIRouter(prefix="/orders", tags=["orders"])


async def _load_order_with_items(order_id: uuid.UUID, db: AsyncSession) -> Order:
    order = await db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.order_items))
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return order


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def place_order(
    payload: OrderPlace,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> Order:
    profile = await get_customer_profile(current_user, db)

    # Validate restaurant
    restaurant = await db.get(Restaurant, payload.restaurant_id)
    if not restaurant or not restaurant.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found",
        )

    # Validate items and calculate totals
    total = Decimal(0)
    order_items_data: List[tuple] = []

    for item in payload.items:
        menu_item = await db.get(MenuItem, item.menu_item_id)
        if not menu_item or menu_item.restaurant_id != payload.restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Menu item {item.menu_item_id} is not available at this restaurant",
            )
        if not menu_item.is_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Menu item {menu_item.name} is currently unavailable",
            )

        unit_price = Decimal(str(menu_item.price))
        subtotal = unit_price * item.quantity
        total += subtotal
        order_items_data.append((menu_item, item.quantity, unit_price, subtotal))

    # Create order
    order = Order(
        customer_id=profile.id,
        restaurant_id=payload.restaurant_id,
        total_amount=total,
        special_instructions=payload.special_instructions,
        status=OrderStatus.PENDING,
    )
    db.add(order)
    await db.flush()

    # Create order items
    for menu_item, quantity, unit_price, subtotal in order_items_data:
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=menu_item.id,
                quantity=quantity,
                unit_price=unit_price,
                subtotal=subtotal,
            )
        )

    await db.commit()
    return await _load_order_with_items(order.id, db)


@router.get("/my", response_model=List[OrderOut])
async def list_my_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> List[Order]:
    profile = await get_customer_profile(current_user, db)
    result = await db.scalars(
        select(Order)
        .where(Order.customer_id == profile.id)
        .options(selectinload(Order.order_items))
        .order_by(Order.created_at.desc())
    )
    return list(result.all())


@router.get("/restaurant/{restaurant_id}", response_model=List[OrderOut])
async def list_restaurant_orders(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
) -> List[Order]:
    restaurant = await db.get(Restaurant, restaurant_id)
    if not restaurant or restaurant.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    result = await db.scalars(
        select(Order)
        .where(Order.restaurant_id == restaurant_id)
        .options(selectinload(Order.order_items))
        .order_by(Order.created_at.desc())
    )
    return list(result.all())


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    order = await _load_order_with_items(order_id, db)

    # Authorization check based on role
    if current_user.role.value == "customer":
        profile = await get_customer_profile(current_user, db)
        if order.customer_id != profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
    elif current_user.role.value == "owner":
        restaurant = await db.get(Restaurant, order.restaurant_id)
        if not restaurant or restaurant.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

    return order


@router.patch("/{order_id}/status", response_model=OrderOut)
async def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
) -> Order:
    order = await _load_order_with_items(order_id, db)

    # Verify ownership
    restaurant = await db.get(Restaurant, order.restaurant_id)
    if not restaurant or restaurant.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Validate status transition
    allowed_transitions = ORDER_STATUS_TRANSITIONS.get(order.status, [])
    if payload.status not in allowed_transitions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot transition from {order.status.value} to {payload.status.value}",
        )

    order.status = payload.status

    # Update menu item order counts when completed
    if payload.status == OrderStatus.COMPLETED:
        for order_item in order.order_items:
            menu_item = await db.get(MenuItem, order_item.menu_item_id)
            if menu_item:
                menu_item.order_count += order_item.quantity

    await db.commit()
    return await _load_order_with_items(order.id, db)
