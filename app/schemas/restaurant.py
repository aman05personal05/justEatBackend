import uuid
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class RestaurantCreate(BaseModel):
    name: str = Field(..., max_length=200)
    cuisine_type: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    image_url: Optional[str] = None


class RestaurantUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    cuisine_type: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class RestaurantOut(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    cuisine_type: Optional[str]
    location: Optional[str]
    description: Optional[str]
    image_url: Optional[str]
    is_active: bool
    rating: Optional[Decimal]

    model_config = {"from_attributes": True}
