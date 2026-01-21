"""Audit log repository for database operations."""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


class AuditLogRepository:
    """Repository for AuditLog database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        action: str,
        resource_type: str,
        user_id: Optional[UUID] = None,
        resource_id: Optional[UUID] = None,
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Create a new audit log entry.

        Args:
            action: Action performed
            resource_type: Type of resource
            user_id: User who performed action
            resource_id: ID of affected resource
            details: Additional details
            ip_address: Client IP address

        Returns:
            Created audit log
        """
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """List audit logs for a user.

        Args:
            user_id: User UUID
            limit: Maximum logs
            offset: Pagination offset

        Returns:
            List of audit logs
        """
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_resource(
        self,
        resource_type: str,
        resource_id: UUID,
        limit: int = 100,
    ) -> list[AuditLog]:
        """List audit logs for a resource.

        Args:
            resource_type: Resource type
            resource_id: Resource UUID
            limit: Maximum logs

        Returns:
            List of audit logs
        """
        result = await self.session.execute(
            select(AuditLog)
            .where(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_queries_today(self) -> int:
        """Count chat queries made today.

        Returns:
            Number of queries today
        """
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await self.session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "chat_query",
                AuditLog.created_at >= today_start,
            )
        )
        return result.scalar_one()

    async def count_active_users_today(self) -> int:
        """Count unique users active today.

        Returns:
            Number of active users today
        """
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await self.session.execute(
            select(func.count(func.distinct(AuditLog.user_id))).where(
                AuditLog.created_at >= today_start,
                AuditLog.user_id.isnot(None),
            )
        )
        return result.scalar_one()
