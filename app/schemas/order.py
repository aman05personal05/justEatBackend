import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.order import OrderStatus


class OrderItemIn(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(..., ge=1)

class OrderPlace(BaseModel):
    restaurant_id: uuid.UUID
    items: List[OrderItemIn] = Field(..., min_length=1)
    special_instructions: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

class OrderItemOut(BaseModel):
    id: uuid.UUID
    menu_item_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    subtotal: Decimal

    model_config = {"from_attributes": True}

class OrderOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    restaurant_id: uuid.UUID
    status: OrderStatus
    total_amount: Decimal
    special_instructions: Optional[str]
    created_at: Optional[datetime] = None
    order_items: List[OrderItemOut] = []

    model_config = {"from_attributes": True}
