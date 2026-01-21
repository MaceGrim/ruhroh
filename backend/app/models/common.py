"""Common Pydantic models and utilities."""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class ErrorDetail(BaseModel):
    """Error detail schema."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict[str, Any]] = Field(None, description="Additional error details")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: list[T]
    total: int
    limit: int
    offset: int


class HealthStatus(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Overall health status")
    database: str = Field(..., description="Database health")
    qdrant: str = Field(..., description="Qdrant health")


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    created_at: datetime
    updated_at: Optional[datetime] = None
