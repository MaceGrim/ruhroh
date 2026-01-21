"""Document Pydantic models."""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.common import BaseSchema


class DocumentUpload(BaseModel):
    """Schema for document upload request."""

    chunking_strategy: Literal["fixed", "semantic"] = Field(
        default="fixed",
        description="Chunking strategy to use",
    )
    ocr_enabled: bool = Field(
        default=False,
        description="Enable OCR for image-based PDFs",
    )
    force_replace: bool = Field(
        default=False,
        description="Replace existing document with same name",
    )


class DocumentResponse(BaseSchema):
    """Schema for document in API responses."""

    id: UUID
    filename: str
    normalized_filename: str
    file_type: Literal["pdf", "txt"]
    file_size: int = Field(..., description="File size in bytes")
    page_count: Optional[int] = None
    status: Literal["pending", "processing", "ready", "failed"]
    chunking_strategy: str
    ocr_enabled: bool
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentResponse):
    """Schema for detailed document response."""

    chunk_count: int = Field(0, description="Number of chunks")
    user_id: UUID


class DocumentStatusResponse(BaseModel):
    """Schema for document status check."""

    status: Literal["pending", "processing", "ready", "failed"]
    progress: Optional[str] = Field(
        None,
        description="Current processing stage",
    )
    error_message: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    """Schema for document upload response."""

    document_id: UUID
    status: Literal["pending"] = "pending"


class DocumentReprocess(BaseModel):
    """Schema for document reprocess request."""

    chunking_strategy: Optional[Literal["fixed", "semantic"]] = None
    ocr_enabled: Optional[bool] = None


class DocumentListResponse(BaseModel):
    """Schema for paginated document list."""

    documents: list[DocumentResponse]
    total: int


class DocumentListParams(BaseModel):
    """Query parameters for document list."""

    status: Optional[Literal["pending", "processing", "ready", "failed"]] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
