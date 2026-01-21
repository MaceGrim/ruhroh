"""Admin Pydantic models."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.user import UserResponse
from app.models.document import DocumentResponse


class AdminStats(BaseModel):
    """Schema for admin statistics."""

    total_users: int
    active_users_today: int
    total_documents: int
    total_queries_today: int
    documents_by_status: dict[str, int] = Field(
        ...,
        description="Count of documents by status",
    )


class AdminUserListParams(BaseModel):
    """Query parameters for admin user list."""

    role: Optional[str] = None
    is_active: Optional[bool] = None


class AdminUserListResponse(BaseModel):
    """Schema for admin user list."""

    users: list[UserResponse]


class AdminDocumentListParams(BaseModel):
    """Query parameters for admin document list."""

    user_id: Optional[UUID] = None
    status: Optional[str] = None


class AdminDocumentListResponse(BaseModel):
    """Schema for admin document list."""

    documents: list[DocumentResponse]


class AdminHealthResponse(BaseModel):
    """Schema for detailed health response."""

    api: str = Field(..., description="API status")
    database: str = Field(..., description="Database status")
    qdrant: str = Field(..., description="Qdrant status")
    supabase: str = Field(..., description="Supabase status")
