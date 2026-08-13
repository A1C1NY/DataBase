"""Contracts for user, transit status, and ingestion administration."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.auth import Role, UserResponse


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: Role = "passenger"
    is_active: bool = True

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AdminUserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class UserPage(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[UserResponse]


class ActiveStatusUpdate(BaseModel):
    is_active: bool


class ActiveStatusResponse(BaseModel):
    id: int
    is_active: bool


class IngestionRunItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    endpoint: str
    trigger_type: str
    request_keyword: str | None
    city_code: str | None
    started_at: datetime
    finished_at: datetime | None
    status: str
    received_count: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    failed_count: int


class IngestionRunDetail(IngestionRunItem):
    error_message: str | None


class IngestionRunPage(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[IngestionRunItem]
