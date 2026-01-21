"""Thread Pydantic models."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.common import BaseSchema


class ThreadCreate(BaseModel):
    """Schema for creating a thread."""

    name: Optional[str] = Field(None, description="Thread name")


class ThreadResponse(BaseSchema):
    """Schema for thread in API responses."""

    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class ThreadDetailResponse(ThreadResponse):
    """Schema for thread with messages."""

    messages: list["MessageResponse"] = Field(default_factory=list)


class ThreadListResponse(BaseModel):
    """Schema for paginated thread list."""

    threads: list[ThreadResponse]
    total: int


class ThreadListParams(BaseModel):
    """Query parameters for thread list."""

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# Import MessageResponse for type hints
from app.models.message import MessageResponse  # noqa: E402

ThreadDetailResponse.model_rebuild()
