import uuid
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class MenuItemCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    price: Decimal = Field(..., gt=0)
    category: Optional[str] = Field(None, max_length=100)
    image_url: Optional[str] = None
    is_available: bool = True
    is_special: bool = False


class MenuItemUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0)
    category: Optional[str] = Field(None, max_length=100)
    image_url: Optional[str] = None
    is_available: Optional[bool] = None
    is_special: Optional[bool] = None


class MenuItemOut(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    name: str
    description: Optional[str]
    price: Decimal
    category: Optional[str]
    image_url: Optional[str]
    is_available: bool
    is_special: bool
    order_count: int

    model_config = {"from_attributes": True}


class MenuItemWithRestaurantOut(MenuItemOut):
    restaurant_name: Optional[str] = None
