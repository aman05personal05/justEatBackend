"""
Seed script — populates the database with demo data.

Run from the backend/ directory:
    Windows : .\\venv\\Scripts\\python.exe -m app.seed
    Unix    : python -m app.seed

Data created
------------
Owners    : 2  (saurabh@justeats.com  pw: Saurabh123!
                arjun@justeats.com    pw: Arjun123!)
Customers : 2  (gunjan@justeats.com   pw: Gunjan123!
                sumit@justeats.com    pw: Sumit123!)
Owner profiles : 2  (full name, phone, bio, cuisine & dietary preferences)
Customer profiles : 2  (full name, phone, dietary restrictions, favourite cuisine)
Restaurants : 4  (2 per owner) — Indian & Asian vegetarian
Menu items  : 14  (3-4 per restaurant, fully vegetarian)
"""
import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure every model is registered with Base.metadata
import app.models.cart  # noqa: F401
import app.models.menu_item  # noqa: F401
import app.models.order  # noqa: F401
import app.models.refresh_token  # noqa: F401
import app.models.restaurant  # noqa: F401
import app.models.user  # noqa: F401
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.menu_item import MenuItem
from app.models.restaurant import Restaurant
from app.models.user import CustomerProfile, OwnerProfile, User, UserRole


async def seed() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        # ── Guard: abort if data already exists ───────────────────────────
        existing = await db.scalar(select(User))
        if existing:
            print("⚠  Database already contains data – skipping seed.")
            return

        # ── Owners ────────────────────────────────────────────────────────
        saurabh = User(
            email="saurabh@justeats.com",
            hashed_password=get_password_hash("Saurabh123!"),
            role=UserRole.owner,
        )
        arjun = User(
            email="arjun@justeats.com",
            hashed_password=get_password_hash("Arjun123!"),
            role=UserRole.owner,
        )

        # ── Customers ─────────────────────────────────────────────────────
        gunjan = User(
            email="gunjan@justeats.com",
            hashed_password=get_password_hash("Gunjan123!"),
            role=UserRole.customer,
        )
        sumit = User(
            email="sumit@justeats.com",
            hashed_password=get_password_hash("Sumit123!"),
            role=UserRole.customer,
        )

        db.add_all([saurabh, arjun, gunjan, sumit])
        await db.flush()

        # ── Customer profiles ─────────────────────────────────────────────
        db.add_all([
            CustomerProfile(
                user_id=gunjan.id,
                full_name="Gunjan Mishra",
                phone="+919876543210",
                dietary_restrictions="vegetarian",
                favourite_cuisine="North Indian",
            ),
            CustomerProfile(
                user_id=sumit.id,
                full_name="Sumit Sarkar",
                phone="+919876543211",
                dietary_restrictions="vegan",
                favourite_cuisine="Asian",
            ),        ])
        await db.flush()

        # ── Owner profiles ────────────────────────────────────────────────────────────────
        db.add_all([
            OwnerProfile(
                user_id=saurabh.id,
                full_name="Saurabh Kumar",
                phone="+919876500001",
                bio="Passionate food entrepreneur with 10+ years running vegetarian kitchens across North and South India.",
                favourite_cuisine="North Indian Vegetarian",
                dietary_restrictions="vegetarian",
            ),
            OwnerProfile(
                user_id=arjun.id,
                full_name="Arjun Vishwakarma",
                phone="+919876500002",
                bio="Plant-based food enthusiast and chef. Loves experimenting with Pan-Asian flavours and Gujarati heritage recipes.",
                favourite_cuisine="Pan-Asian Vegetarian",
                dietary_restrictions="vegan",
            ),
        ])
        await db.flush()       
        await db.flush()

        # ── Restaurants (2 per owner = 4 total) ───────────────────────────

        # Saurabh Kumar's restaurants
        punjab_da_dhaba = Restaurant(
            owner_id=saurabh.id,
            name="Punjab Da Dhaba",
            cuisine_type="North Indian Vegetarian",
            location="Connaught Place, New Delhi",
            description="Authentic Punjabi veg fare — dal makhani, paneer dishes and freshly baked tandoori breads, just like back home.",
            rating=Decimal("4.6"),
        )
        udupi_paradise = Restaurant(
            owner_id=saurabh.id,
            name="Udupi Paradise",
            cuisine_type="South Indian Vegetarian",
            location="Indiranagar, Bengaluru",
            description="Pure-veg South Indian tiffin house serving crispy dosas, fluffy idlis and fresh coconut chutneys since 1991.",
            rating=Decimal("4.4"),
        )

        # Arjun Vishwakarma's restaurants
        buddha_bowl = Restaurant(
            owner_id=arjun.id,
            name="Buddha Bowl — Asian Veg Kitchen",
            cuisine_type="Pan-Asian Vegetarian",
            location="Bandra West, Mumbai",
            description="Plant-based Pan-Asian kitchen blending Japanese, Thai and Chinese flavours into nourishing, vibrant bowls.",
            rating=Decimal("4.7"),
        )
        gujarati_thali_house = Restaurant(
            owner_id=arjun.id,
            name="Shree Gujarati Thali House",
            cuisine_type="Gujarati Vegetarian",
            location="Navrangpura, Ahmedabad",
            description="Unlimited traditional Gujarati thali with seasonal shaak, dal, kadhi, rotli and a rotating selection of farsan.",
            rating=Decimal("4.5"),
        )

        db.add_all([punjab_da_dhaba, udupi_paradise, buddha_bowl, gujarati_thali_house])
        await db.flush()

        # ── Menu items (14 total, ≥ 3 per restaurant, 100 % vegetarian) ───
        db.add_all([
            # ── Punjab Da Dhaba ──────────────────────────────────────────
            MenuItem(
                restaurant_id=punjab_da_dhaba.id,
                name="Dal Makhani",
                description="Black lentils slow-cooked overnight with butter and cream — the pride of Punjabi kitchens.",
                price=Decimal("180.00"), category="Mains",
                is_available=True, is_special=True,
            ),
            MenuItem(
                restaurant_id=punjab_da_dhaba.id,
                name="Paneer Butter Masala",
                description="Cottage cheese cubes in a velvety tomato-cashew gravy, mildly spiced.",
                price=Decimal("220.00"), category="Mains", is_available=True,
            ),
            MenuItem(
                restaurant_id=punjab_da_dhaba.id,
                name="Stuffed Tandoori Paratha",
                description="Whole-wheat flatbread stuffed with spiced aloo or paneer, baked in the clay oven.",
                price=Decimal("60.00"), category="Breads", is_available=True,
            ),
            MenuItem(
                restaurant_id=punjab_da_dhaba.id,
                name="Lassi (Sweet / Salted)",
                description="Chilled yoghurt drink churned with rose water and a pinch of cardamom.",
                price=Decimal("80.00"), category="Drinks", is_available=True,
            ),

            # ── Udupi Paradise ───────────────────────────────────────────
            MenuItem(
                restaurant_id=udupi_paradise.id,
                name="Masala Dosa",
                description="Crispy rice-and-lentil crêpe filled with spiced potato masala, served with sambar and three chutneys.",
                price=Decimal("120.00"), category="Tiffin",
                is_available=True, is_special=True,
            ),
            MenuItem(
                restaurant_id=udupi_paradise.id,
                name="Idli Sambar (3 pcs)",
                description="Steamed fermented rice cakes paired with piping-hot lentil sambar and fresh coconut chutney.",
                price=Decimal("90.00"), category="Tiffin", is_available=True,
            ),
            MenuItem(
                restaurant_id=udupi_paradise.id,
                name="Medu Vada",
                description="Golden, crunchy lentil doughnuts with a fluffy interior — best dunked in sambar.",
                price=Decimal("80.00"), category="Snacks", is_available=True,
            ),

            # ── Buddha Bowl — Asian Veg Kitchen ─────────────────────────
            MenuItem(
                restaurant_id=buddha_bowl.id,
                name="Thai Green Curry Bowl",
                description="Fragrant lemongrass and kaffir lime green curry with seasonal vegetables and jasmine rice.",
                price=Decimal("310.00"), category="Bowls",
                is_available=True, is_special=True,
            ),
            MenuItem(
                restaurant_id=buddha_bowl.id,
                name="Tofu Pad Thai",
                description="Stir-fried rice noodles with tofu, bean sprouts, spring onion, tamarind and crushed peanuts.",
                price=Decimal("290.00"), category="Noodles", is_available=True,
            ),
            MenuItem(
                restaurant_id=buddha_bowl.id,
                name="Veggie Gyoza (6 pcs)",
                description="Pan-fried Japanese dumplings stuffed with cabbage, shiitake mushroom and ginger.",
                price=Decimal("220.00"), category="Starters", is_available=True,
            ),
            MenuItem(
                restaurant_id=buddha_bowl.id,
                name="Matcha Mochi Ice Cream",
                description="Soft glutinous rice cake filled with premium Uji matcha ice cream.",
                price=Decimal("150.00"), category="Desserts", is_available=True,
            ),

            # ── Shree Gujarati Thali House ───────────────────────────────
            MenuItem(
                restaurant_id=gujarati_thali_house.id,
                name="Full Gujarati Thali (Unlimited)",
                description="Rotating seasonal spread — dal, kadhi, 3 shaak, rotli, bhaat, pickles, papad and a sweet.",
                price=Decimal("250.00"), category="Thali",
                is_available=True, is_special=True,
            ),
            MenuItem(
                restaurant_id=gujarati_thali_house.id,
                name="Dhokla",
                description="Steamed fermented chickpea-flour cakes tempered with mustard seeds and curry leaves.",
                price=Decimal("80.00"), category="Farsan", is_available=True,
            ),
            MenuItem(
                restaurant_id=gujarati_thali_house.id,
                name="Shrikhand",
                description="Strained yoghurt sweetened with sugar and flavoured with saffron and cardamom.",
                price=Decimal("90.00"), category="Sweets", is_available=True,
            ),
        ])

        await db.commit()

    await engine.dispose()

    print("✓ Seed complete:")
    print("  • 2 owners:")
    print("      Saurabh Kumar  — saurabh@justeats.com  (pw: Saurabh123!)")
    print("      Arjun Vishwakarma — arjun@justeats.com (pw: Arjun123!)")
    print("  • 2 customers:")
    print("      Gunjan Mishra  — gunjan@justeats.com   (pw: Gunjan123!)")
    print("      Sumit Sarkar   — sumit@justeats.com    (pw: Sumit123!)")
    print("  • 4 Indian & Asian veg restaurants, 14 menu items")


if __name__ == "__main__":
    asyncio.run(seed())
