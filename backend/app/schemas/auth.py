"""Authentication, current-user, and favorite response contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.transit import LineItem, StopItem

Role = Literal["passenger", "analyst", "admin"]


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Role
    is_active: bool
    # Database-backed users always have this value; the default keeps transient
    # ORM instances (before refresh) serializable in internal flows/tests.
    created_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class FavoriteStopItem(BaseModel):
    created_at: datetime
    stop: StopItem


class FavoriteLineItem(BaseModel):
    created_at: datetime
    line: LineItem


class FavoriteStopListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[FavoriteStopItem]


class FavoriteLineListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[FavoriteLineItem]
