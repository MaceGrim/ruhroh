"""Chunk Pydantic models."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.common import BaseSchema


class ChunkResponse(BaseSchema):
    """Schema for chunk in API responses."""

    id: UUID
    document_id: UUID
    content: str
    chunk_index: int
    page_numbers: Optional[list[int]] = None
    start_offset: int
    end_offset: int
    token_count: int
    extracted_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ChunkCreate(BaseModel):
    """Schema for creating a chunk (internal use)."""

    document_id: UUID
    content: str
    chunk_index: int
    page_numbers: Optional[list[int]] = None
    start_offset: int
    end_offset: int
    token_count: int
    extracted_metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    """Schema for search result."""

    chunk_id: UUID
    document_id: UUID
    document_name: str
    content: str
    page_numbers: Optional[list[int]] = None
    score: float = Field(..., description="Relevance score")
    highlight_offsets: Optional[dict[str, int]] = Field(
        None,
        description="Start and end positions of matching text",
    )


class SearchRequest(BaseModel):
    """Schema for search request."""

    query: str = Field(..., min_length=1, description="Search query")
    top_k: int = Field(default=10, ge=1, le=100, description="Max results")
    document_ids: Optional[list[UUID]] = Field(
        None,
        description="Filter to specific documents",
    )
    use_keyword: bool = Field(default=True, description="Use keyword search")
    use_vector: bool = Field(default=True, description="Use vector search")


class SearchResponse(BaseModel):
    """Schema for search response."""

    results: list[SearchResult]
