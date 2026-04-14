from typing import Optional
from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: Optional[str] = None
    note: Optional[str] = None


class AddedToFavouritesResponse(BaseModel):
    detail: str
