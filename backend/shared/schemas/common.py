"""Shared primitives used by all component schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMBase(BaseModel):
    """Base for schemas that hydrate from SQLAlchemy ORM objects."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class TimestampedSchema(ORMBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1, default=1)
    page_size: int = Field(ge=1, le=200, default=20)


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    error: str
    details: list[ErrorDetail] = Field(default_factory=list)


class RiskTolerance(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Currency(StrEnum):
    LKR = "LKR"
    USD = "USD"


__all__ = [
    "Currency",
    "ErrorDetail",
    "ErrorResponse",
    "ORMBase",
    "PaginatedResponse",
    "RiskTolerance",
    "TimestampedSchema",
]
