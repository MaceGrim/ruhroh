"""Admin API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.database import get_db_session
from app.db.models import User
from app.dependencies import require_role
from app.models import (
    AdminStats,
    AdminUserListResponse,
    AdminDocumentListResponse,
    AdminHealthResponse,
    UserResponse,
    UserUpdate,
    DocumentResponse,
    ErrorResponse,
)
from app.services.admin import AdminService
from app.services.qdrant import check_qdrant_health
from app.db.database import check_db_health

router = APIRouter()


async def get_admin_service(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminService:
    """Get admin service."""
    return AdminService(settings, db)


require_admin_role = require_role(["admin"])
require_superuser_role = require_role(["superuser", "admin"])


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    dependencies=[Depends(require_admin_role)],
)
async def list_users(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    role: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
):
    """List all users (admin only)."""
    users = await admin_service.list_users(role=role, is_active=is_active)

    return AdminUserListResponse(
        users=[
            UserResponse(
                id=UUID(u["id"]),
                email=u["email"],
                role=u["role"],
                created_at=u["created_at"],
                last_login=u["last_login"],
                is_active=u["is_active"],
            )
            for u in users
        ]
    )


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_admin_role)],
    responses={404: {"model": ErrorResponse}},
)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
):
    """Update a user's role or status (admin only)."""
    result = await admin_service.update_user(
        user_id,
        role=data.role,
        is_active=data.is_active,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "User not found"},
        )

    return UserResponse(
        id=UUID(result["id"]),
        email=result["email"],
        role=result["role"],
        created_at=result["created_at"],
        last_login=result["last_login"],
        is_active=result["is_active"],
    )


@router.get(
    "/stats",
    response_model=AdminStats,
    dependencies=[Depends(require_superuser_role)],
)
async def get_stats(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
):
    """Get system statistics (superuser or admin)."""
    stats = await admin_service.get_stats()

    return AdminStats(
        total_users=stats["total_users"],
        active_users_today=stats["active_users_today"],
        total_documents=stats["total_documents"],
        total_queries_today=stats["total_queries_today"],
        documents_by_status=stats["documents_by_status"],
    )


@router.get(
    "/documents",
    response_model=AdminDocumentListResponse,
    dependencies=[Depends(require_admin_role)],
)
async def list_all_documents(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    user_id: Annotated[UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
):
    """List all documents (admin only)."""
    documents = await admin_service.list_all_documents(
        user_id=user_id,
        status=status_filter,
    )

    return AdminDocumentListResponse(
        documents=[
            DocumentResponse(
                id=UUID(d["id"]),
                filename=d["filename"],
                normalized_filename=d["filename"].lower(),
                file_type=d["file_type"],
                file_size=d["file_size"],
                page_count=d["page_count"],
                status=d["status"],
                chunking_strategy="fixed",
                ocr_enabled=False,
                error_message=d["error_message"],
                created_at=d["created_at"],
                updated_at=d["updated_at"],
            )
            for d in documents
        ]
    )


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_role)],
    responses={404: {"model": ErrorResponse}},
)
async def admin_delete_document(
    document_id: UUID,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
):
    """Delete any document (admin only)."""
    deleted = await admin_service.delete_document(document_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Document not found"},
        )

    return None


@router.get(
    "/health",
    response_model=AdminHealthResponse,
)
async def admin_health(
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Get detailed system health status."""
    db_healthy = await check_db_health()
    qdrant_healthy = await check_qdrant_health()

    # Check Supabase
    supabase_healthy = True
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.supabase_url}/auth/v1/health")
            supabase_healthy = response.status_code == 200
    except Exception:
        supabase_healthy = False

    all_healthy = db_healthy and qdrant_healthy and supabase_healthy

    return AdminHealthResponse(
        api="ok" if all_healthy else "degraded",
        database="ok" if db_healthy else "error",
        qdrant="ok" if qdrant_healthy else "error",
        supabase="ok" if supabase_healthy else "error",
    )
