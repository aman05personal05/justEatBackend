import uuid
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class CartItemAdd(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1)


class CartItemOut(BaseModel):
    id: uuid.UUID
    menu_item_id: uuid.UUID
    quantity: int
    name: Optional[str] = None
    unit_price: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None

    model_config = {"from_attributes": True}
