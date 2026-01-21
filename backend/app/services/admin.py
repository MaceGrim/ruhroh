"""Admin service for system management."""

from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.repositories.user import UserRepository
from app.db.repositories.document import DocumentRepository
from app.db.repositories.audit import AuditLogRepository

logger = structlog.get_logger()


class AdminService:
    """Service for admin operations."""

    def __init__(self, settings: Settings, session: AsyncSession):
        self.settings = settings
        self.session = session
        self.user_repo = UserRepository(session)
        self.doc_repo = DocumentRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def get_stats(self) -> dict:
        """Get system statistics.

        Returns:
            Dict with system stats
        """
        total_users = await self.user_repo.count()
        active_users_today = await self.audit_repo.count_active_users_today()
        total_documents = await self._count_all_documents()
        total_queries_today = await self.audit_repo.count_queries_today()
        documents_by_status = await self.doc_repo.count_by_status()

        return {
            "total_users": total_users,
            "active_users_today": active_users_today,
            "total_documents": total_documents,
            "total_queries_today": total_queries_today,
            "documents_by_status": documents_by_status,
        }

    async def _count_all_documents(self) -> int:
        """Count all documents in the system.

        Returns:
            Total document count
        """
        status_counts = await self.doc_repo.count_by_status()
        return sum(status_counts.values())

    async def list_users(
        self,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[dict]:
        """List all users with optional filters.

        Args:
            role: Filter by role
            is_active: Filter by active status

        Returns:
            List of user dicts
        """
        users = await self.user_repo.list_all(role=role, is_active=is_active)

        return [
            {
                "id": str(u.id),
                "email": u.email,
                "role": u.role,
                "created_at": u.created_at.isoformat(),
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "is_active": u.is_active,
            }
            for u in users
        ]

    async def update_user(
        self,
        user_id: UUID,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[dict]:
        """Update a user's role or status.

        Args:
            user_id: User UUID
            role: New role
            is_active: New active status

        Returns:
            Updated user dict or None
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None

        if role is not None:
            user = await self.user_repo.update_role(user_id, role)

        if is_active is not None:
            user = await self.user_repo.set_active(user_id, is_active)

        if not user:
            return None

        logger.info(
            "user_updated_by_admin",
            user_id=str(user_id),
            role=role,
            is_active=is_active,
        )

        return {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "is_active": user.is_active,
        }

    async def list_all_documents(
        self,
        user_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        """List all documents with optional filters.

        Args:
            user_id: Filter by user
            status: Filter by status

        Returns:
            List of document dicts
        """
        documents = await self.doc_repo.list_all(user_id=user_id, status=status)

        return [
            {
                "id": str(d.id),
                "user_id": str(d.user_id),
                "filename": d.filename,
                "file_type": d.file_type,
                "file_size": d.file_size,
                "page_count": d.page_count,
                "status": d.status,
                "error_message": d.error_message,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
            }
            for d in documents
        ]

    async def delete_document(self, document_id: UUID) -> bool:
        """Delete any document (admin only).

        Args:
            document_id: Document UUID

        Returns:
            True if deleted
        """
        deleted = await self.doc_repo.delete(document_id)

        if deleted:
            logger.info(
                "document_deleted_by_admin",
                document_id=str(document_id),
            )

        return deleted

    async def log_action(
        self,
        action: str,
        resource_type: str,
        user_id: Optional[UUID] = None,
        resource_id: Optional[UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log an admin action.

        Args:
            action: Action performed
            resource_type: Type of resource
            user_id: User who performed action
            resource_id: Affected resource ID
            details: Additional details
            ip_address: Client IP
        """
        await self.audit_repo.create(
            action=action,
            resource_type=resource_type,
            user_id=user_id,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
