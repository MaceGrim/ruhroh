"""Message Pydantic models."""

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
import re

from app.models.common import BaseSchema


class Citation(BaseModel):
    """Schema for a citation in a message."""

    index: int = Field(..., description="Citation number [1], [2], etc.")
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page: Optional[int] = None
    excerpt: str = Field(..., description="Relevant text excerpt")


class MessageCreate(BaseModel):
    """Schema for creating a message."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Message content",
    )
    model: Optional[str] = Field(
        None,
        description="LLM model to use (optional, uses default)",
    )

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        """Sanitize message content."""
        # Strip HTML tags
        v = re.sub(r"<[^>]+>", "", v)
        return v.strip()


class MessageResponse(BaseSchema):
    """Schema for message in API responses."""

    id: UUID
    thread_id: UUID
    role: Literal["user", "assistant"]
    content: str
    citations: Optional[list[Citation]] = None
    model_used: Optional[str] = None
    is_from_documents: bool = True
    token_count: Optional[int] = None
    created_at: datetime


class StreamEvent(BaseModel):
    """Base schema for SSE stream events."""

    event: str
    data: dict[str, Any]


class StatusEvent(BaseModel):
    """Schema for status SSE event."""

    stage: Literal["searching", "thinking", "generating"]


class TokenEvent(BaseModel):
    """Schema for token SSE event."""

    content: str


class CitationEvent(BaseModel):
    """Schema for citation SSE event."""

    index: int
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page: Optional[int] = None
    excerpt: str


class DoneEvent(BaseModel):
    """Schema for done SSE event."""

    message_id: UUID
    is_from_documents: bool


class ErrorEvent(BaseModel):
    """Schema for error SSE event."""

    code: str
    message: str
