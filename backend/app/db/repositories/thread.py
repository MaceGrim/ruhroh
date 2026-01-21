"""Thread repository for database operations."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Thread, Message


class ThreadRepository:
    """Repository for Thread database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        thread_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[Thread]:
        """Get thread by ID.

        Args:
            thread_id: Thread UUID
            user_id: Optional user ID for ownership check

        Returns:
            Thread if found
        """
        query = select(Thread).where(Thread.id == thread_id)
        if user_id is not None:
            query = query.where(Thread.user_id == user_id)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_with_messages(
        self,
        thread_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[Thread]:
        """Get thread by ID with messages.

        Args:
            thread_id: Thread UUID
            user_id: Optional user ID for ownership check

        Returns:
            Thread with messages if found
        """
        query = (
            select(Thread)
            .options(selectinload(Thread.messages))
            .where(Thread.id == thread_id)
        )
        if user_id is not None:
            query = query.where(Thread.user_id == user_id)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: UUID,
        name: str = "New Conversation",
    ) -> Thread:
        """Create a new thread.

        Args:
            user_id: Owner user ID
            name: Thread name

        Returns:
            Created thread
        """
        thread = Thread(user_id=user_id, name=name)
        self.session.add(thread)
        await self.session.flush()
        return thread

    async def update_name(
        self,
        thread_id: UUID,
        name: str,
    ) -> Optional[Thread]:
        """Update thread name.

        Args:
            thread_id: Thread UUID
            name: New name

        Returns:
            Updated thread
        """
        await self.session.execute(
            update(Thread)
            .where(Thread.id == thread_id)
            .values(name=name, updated_at=datetime.utcnow())
        )
        return await self.get_by_id(thread_id)

    async def touch(self, thread_id: UUID) -> None:
        """Update thread's updated_at timestamp.

        Args:
            thread_id: Thread UUID
        """
        await self.session.execute(
            update(Thread)
            .where(Thread.id == thread_id)
            .values(updated_at=datetime.utcnow())
        )

    async def delete(self, thread_id: UUID) -> bool:
        """Delete a thread.

        Args:
            thread_id: Thread UUID

        Returns:
            True if deleted
        """
        result = await self.session.execute(
            delete(Thread).where(Thread.id == thread_id)
        )
        return result.rowcount > 0

    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Thread]:
        """List threads for a user.

        Args:
            user_id: User UUID
            limit: Maximum threads
            offset: Pagination offset

        Returns:
            List of threads ordered by update time
        """
        result = await self.session.execute(
            select(Thread)
            .where(Thread.user_id == user_id)
            .order_by(Thread.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: UUID) -> int:
        """Count threads for a user.

        Args:
            user_id: User UUID

        Returns:
            Number of threads
        """
        result = await self.session.execute(
            select(func.count(Thread.id)).where(Thread.user_id == user_id)
        )
        return result.scalar_one()
