import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.restaurant import Restaurant
    from app.models.refresh_token import RefreshToken
    from app.models.order import Order
    from app.models.cart import CartItem
    from app.models.restaurant import FavouriteRestaurant


class UserRole(str, PyEnum):
    customer = "customer"
    owner = "owner"


class User(Base, TimestampMixin):

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Password reset fields — token is hashed before storage for security
    reset_token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reset_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Profile relationship — one per user, role-dependent
    customer_profile: Mapped[Optional["CustomerProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    owner_profile: Mapped[Optional["OwnerProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    # Other relationships
    restaurants: Mapped[List["Restaurant"]] = relationship(back_populates="owner")
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class CustomerProfile(Base, TimestampMixin):

    __tablename__ = "customer_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    # Basic personal info
    full_name: Mapped[Optional[str]] = mapped_column(String(200))
    phone: Mapped[Optional[str]] = mapped_column(String(20))

    # Food preferences — used for recommendations and filtering
    favourite_cuisine: Mapped[Optional[str]] = mapped_column(String(200))
    dietary_restrictions: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="customer_profile")
    orders: Mapped[List["Order"]] = relationship(back_populates="customer")
    cart_items: Mapped[List["CartItem"]] = relationship(back_populates="customer")
    favourite_restaurants: Mapped[List["FavouriteRestaurant"]] = relationship(back_populates="customer")


class OwnerProfile(Base, TimestampMixin):

    __tablename__ = "owner_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    # Basic personal info
    full_name: Mapped[Optional[str]] = mapped_column(String(200))
    phone: Mapped[Optional[str]] = mapped_column(String(20))

    # A short bio shown on their restaurant listings
    bio: Mapped[Optional[str]] = mapped_column(String(1000))

    # Personal food preferences (same fields as customers for consistency)
    favourite_cuisine: Mapped[Optional[str]] = mapped_column(String(200))
    dietary_restrictions: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationship back to the User account
    user: Mapped["User"] = relationship(back_populates="owner_profile")
 