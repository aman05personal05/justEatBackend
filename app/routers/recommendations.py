from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.dependencies import require_role
from app.models.menu_item import MenuItem
from app.models.order import Order, OrderItem, OrderStatus
from app.models.restaurant import Restaurant
from app.models.user import CustomerProfile, User
from app.schemas.menu_item import MenuItemOut, MenuItemWithRestaurantOut
from app.schemas.restaurant import RestaurantOut

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

# Maximum number of recommendations to return
MAX_RECOMMENDATIONS = 10
MAX_MENU_RECOMMENDATIONS = 6


@router.get("", response_model=List[RestaurantOut])
async def get_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> List[Restaurant]:
    # Get customer profile
    profile = await db.scalar(
        select(CustomerProfile).where(CustomerProfile.user_id == current_user.id)
    )

    if profile:
        # Find restaurants ordered from, grouped by frequency
        order_counts = await db.execute(
            select(
                Order.restaurant_id,
                func.count(Order.id).label("order_count"),
            )
            .where(
                Order.customer_id == profile.id,
                Order.status == OrderStatus.COMPLETED,
            )
            .group_by(Order.restaurant_id)
            .order_by(desc("order_count"))
            .limit(MAX_RECOMMENDATIONS)
        )
        rows = order_counts.all()

        if rows:
            # Fetch restaurant details and maintain order
            restaurant_ids = [row.restaurant_id for row in rows]
            restaurants = (
                await db.scalars(
                    select(Restaurant).where(
                        Restaurant.id.in_(restaurant_ids),
                        Restaurant.is_active.is_(True),
                    )
                )
            ).all()

            # Sort by original order count ranking
            id_to_rank = {
                row.restaurant_id: idx for idx, row in enumerate(rows)
            }
            return sorted(
                restaurants,
                key=lambda r: id_to_rank.get(r.id, 999),
            )

    # Fallback: top-rated restaurants
    top_rated = await db.scalars(
        select(Restaurant)
        .where(
            Restaurant.is_active.is_(True),
            Restaurant.rating.isnot(None),
        )
        .order_by(desc(Restaurant.rating))
        .limit(MAX_RECOMMENDATIONS)
    )
    return list(top_rated.all())


@router.get("/menu-items", response_model=List[MenuItemWithRestaurantOut])
async def get_menu_item_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> List[dict]:
    # Get customer profile
    profile = await db.scalar(
        select(CustomerProfile).where(CustomerProfile.user_id == current_user.id)
    )

    items_with_restaurants = []

    if profile:
        # Find menu items ordered most frequently by this customer
        item_counts = await db.execute(
            select(
                OrderItem.menu_item_id,
                func.sum(OrderItem.quantity).label("total_quantity"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.customer_id == profile.id,
                Order.status == OrderStatus.COMPLETED,
            )
            .group_by(OrderItem.menu_item_id)
            .order_by(desc("total_quantity"))
            .limit(MAX_MENU_RECOMMENDATIONS)
        )
        rows = item_counts.all()

        if rows:
            # Fetch menu item details with restaurant info
            item_ids = [row.menu_item_id for row in rows]
            items = (
                await db.scalars(
                    select(MenuItem)
                    .options(selectinload(MenuItem.restaurant))
                    .join(Restaurant, Restaurant.id == MenuItem.restaurant_id)
                    .where(
                        MenuItem.id.in_(item_ids),
                        MenuItem.is_available.is_(True),
                        Restaurant.is_active.is_(True),
                    )
                )
            ).all()

            # Sort by original order count ranking
            id_to_rank = {row.menu_item_id: idx for idx, row in enumerate(rows)}
            sorted_items = sorted(items, key=lambda i: id_to_rank.get(i.id, 999))
            
            for item in sorted_items:
                item_dict = {
                    "id": item.id,
                    "restaurant_id": item.restaurant_id,
                    "name": item.name,
                    "description": item.description,
                    "price": item.price,
                    "category": item.category,
                    "image_url": item.image_url,
                    "is_available": item.is_available,
                    "is_special": item.is_special,
                    "order_count": item.order_count,
                    "restaurant_name": item.restaurant.name if item.restaurant else None,
                }
                items_with_restaurants.append(item_dict)
            
            return items_with_restaurants

    # Fallback: most popular items across all restaurants
    popular_items = (
        await db.scalars(
            select(MenuItem)
            .options(selectinload(MenuItem.restaurant))
            .join(Restaurant, Restaurant.id == MenuItem.restaurant_id)
            .where(
                MenuItem.is_available.is_(True),
                Restaurant.is_active.is_(True),
            )
            .order_by(desc(MenuItem.order_count))
            .limit(MAX_MENU_RECOMMENDATIONS)
        )
    ).all()
    
    for item in popular_items:
        item_dict = {
            "id": item.id,
            "restaurant_id": item.restaurant_id,
            "name": item.name,
            "description": item.description,
            "price": item.price,
            "category": item.category,
            "image_url": item.image_url,
            "is_available": item.is_available,
            "is_special": item.is_special,
            "order_count": item.order_count,
            "restaurant_name": item.restaurant.name if item.restaurant else None,
        }
        items_with_restaurants.append(item_dict)
    
    return items_with_restaurants
