from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import CustomerProfile, OwnerProfile, User

# ─── Customer profile helpers ───────────────────────────────────────────

async def get_customer_profile(user: User, db: AsyncSession) -> CustomerProfile:
    # Try to find an existing profile for this user
    profile = await db.scalar(
        select(CustomerProfile).where(CustomerProfile.user_id == user.id)
    )

    # No profile? Let them know they need to create one first
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You don't have a profile yet. Please visit your profile page to set one up.",
        )

    return profile


async def get_or_create_profile(user: User, db: AsyncSession) -> CustomerProfile:
    # Check if they already have a profile
    existing_profile = await db.scalar(
        select(CustomerProfile).where(CustomerProfile.user_id == user.id)
    )

    if existing_profile:
        return existing_profile

    # No profile yet - let's create a blank one for them
    new_profile = CustomerProfile(user_id=user.id)
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)  # Get the auto-generated ID and timestamps

    return new_profile


# ─── Owner profile helpers ───────────────────────────────────────────

async def get_or_create_owner_profile(user: User, db: AsyncSession) -> OwnerProfile:
    existing_profile = await db.scalar(
        select(OwnerProfile).where(OwnerProfile.user_id == user.id)
    )

    if existing_profile:
        return existing_profile

    # First visit — create a blank profile so the page has something to show
    new_profile = OwnerProfile(user_id=user.id)
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return new_profile
