from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import require_role
from app.models.user import CustomerProfile, OwnerProfile, User
from app.schemas.profile import (
    OwnerProfileOut,
    OwnerProfileUpdate,
    ProfileOut,
    ProfileUpdate,
)
from app.services import get_or_create_owner_profile, get_or_create_profile

router = APIRouter(prefix="/profile", tags=["profile"])


# ─── Customer endpoints ───────────────────────────────────────────────────────

@router.get("", response_model=ProfileOut)
async def get_customer_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> CustomerProfile:
    return await get_or_create_profile(current_user, db)


@router.patch("", response_model=ProfileOut)
async def update_customer_profile(
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
) -> CustomerProfile:
    profile = await get_or_create_profile(current_user, db)

    # Apply only the fields that were actually sent in the request
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile


# ─── Owner endpoints ──────────────────────────────────────────────────────────

@router.get("/owner", response_model=OwnerProfileOut)
async def get_owner_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
) -> OwnerProfile:
    return await get_or_create_owner_profile(current_user, db)


@router.patch("/owner", response_model=OwnerProfileOut)
async def update_owner_profile(
    payload: OwnerProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
) -> OwnerProfile:

    profile = await get_or_create_owner_profile(current_user, db)

    # Apply only the fields that were actually sent in the request
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile
