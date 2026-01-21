"""Message repository for database operations."""

from typing import Any, Literal, Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message


class MessageRepository:
    """Repository for Message database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, message_id: UUID) -> Optional[Message]:
        """Get message by ID.

        Args:
            message_id: Message UUID

        Returns:
            Message if found
        """
        result = await self.session.execute(
            select(Message).where(Message.id == message_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        thread_id: UUID,
        role: Literal["user", "assistant"],
        content: str,
        citations: Optional[list[dict[str, Any]]] = None,
        model_used: Optional[str] = None,
        is_from_documents: bool = True,
        token_count: Optional[int] = None,
    ) -> Message:
        """Create a new message.

        Args:
            thread_id: Thread UUID
            role: Message role (user/assistant)
            content: Message content
            citations: Optional citations
            model_used: Optional model identifier
            is_from_documents: Whether response is from documents
            token_count: Optional token count

        Returns:
            Created message
        """
        message = Message(
            thread_id=thread_id,
            role=role,
            content=content,
            citations=citations,
            model_used=model_used,
            is_from_documents=is_from_documents,
            token_count=token_count,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def delete(self, message_id: UUID) -> bool:
        """Delete a message.

        Args:
            message_id: Message UUID

        Returns:
            True if deleted
        """
        result = await self.session.execute(
            delete(Message).where(Message.id == message_id)
        )
        return result.rowcount > 0

    async def list_by_thread(
        self,
        thread_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        """List messages for a thread.

        Args:
            thread_id: Thread UUID
            limit: Maximum messages
            offset: Pagination offset

        Returns:
            List of messages ordered by creation time
        """
        result = await self.session.execute(
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_thread(self, thread_id: UUID) -> int:
        """Count messages for a thread.

        Args:
            thread_id: Thread UUID

        Returns:
            Number of messages
        """
        result = await self.session.execute(
            select(func.count(Message.id)).where(Message.thread_id == thread_id)
        )
        return result.scalar_one()

    async def get_last_messages(
        self,
        thread_id: UUID,
        count: int = 10,
    ) -> list[Message]:
        """Get last N messages from a thread.

        Args:
            thread_id: Thread UUID
            count: Number of messages

        Returns:
            List of most recent messages in chronological order
        """
        result = await self.session.execute(
            select(Message)
            .where(Message.thread_id == thread_id)
            # Use id as tiebreaker for deterministic ordering when timestamps match
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(count)
        )
        messages = list(result.scalars().all())
        # Reverse to get chronological order
        return messages[::-1]
