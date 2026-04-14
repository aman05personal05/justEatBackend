import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User, CustomerProfile
    from app.models.menu_item import MenuItem
    from app.models.order import Order


class Restaurant(Base, TimestampMixin):
    __tablename__ = "restaurants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    cuisine_type: Mapped[Optional[str]] = mapped_column(String(100))
    location: Mapped[Optional[str]] = mapped_column(String(300))
    description: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rating: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))

    owner: Mapped["User"] = relationship(back_populates="restaurants")
    menu_items: Mapped[List["MenuItem"]] = relationship(back_populates="restaurant", cascade="all, delete-orphan")
    orders: Mapped[List["Order"]] = relationship(back_populates="restaurant")
    favourited_by: Mapped[List["FavouriteRestaurant"]] = relationship(back_populates="restaurant", cascade="all, delete-orphan")


class FavouriteRestaurant(Base):

    __tablename__ = "favourite_restaurants"
    __table_args__ = (UniqueConstraint("customer_id", "restaurant_id", name="uq_fav_customer_restaurant"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    customer: Mapped["CustomerProfile"] = relationship(back_populates="favourite_restaurants")
    restaurant: Mapped["Restaurant"] = relationship(back_populates="favourited_by")
