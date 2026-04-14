from app.routers.auth import router as auth_router
from app.routers.restaurants import router as restaurants_router
from app.routers.menu_items import router as menu_items_router
from app.routers.cart import router as cart_router
from app.routers.orders import router as orders_router
from app.routers.profile import router as profile_router
from app.routers.favourites import router as favourites_router
from app.routers.recommendations import router as recommendations_router

__all__ = [
    "auth_router", "restaurants_router", "menu_items_router",
    "cart_router", "orders_router", "profile_router",
    "favourites_router", "recommendations_router",
]
