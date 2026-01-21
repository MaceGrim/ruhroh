"""User repository for database operations."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserRepository:
    """Repository for User database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID.

        Args:
            user_id: User UUID

        Returns:
            User if found, None otherwise
        """
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email.

        Args:
            email: User email

        Returns:
            User if found, None otherwise
        """
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: UUID,
        email: str,
        role: str = "user",
    ) -> User:
        """Create a new user.

        Args:
            user_id: User UUID (from Supabase)
            email: User email
            role: User role (default: 'user')

        Returns:
            Created user
        """
        user = User(
            id=user_id,
            email=email,
            role=role,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_last_login(self, user_id: UUID) -> None:
        """Update user's last login timestamp.

        Args:
            user_id: User UUID
        """
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login=datetime.utcnow())
        )

    async def update_role(self, user_id: UUID, role: str) -> Optional[User]:
        """Update user's role.

        Args:
            user_id: User UUID
            role: New role

        Returns:
            Updated user if found
        """
        await self.session.execute(
            update(User).where(User.id == user_id).values(role=role)
        )
        return await self.get_by_id(user_id)

    async def set_active(self, user_id: UUID, is_active: bool) -> Optional[User]:
        """Set user's active status.

        Args:
            user_id: User UUID
            is_active: New active status

        Returns:
            Updated user if found
        """
        await self.session.execute(
            update(User).where(User.id == user_id).values(is_active=is_active)
        )
        return await self.get_by_id(user_id)

    async def list_all(
        self,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[User]:
        """List all users with optional filtering.

        Args:
            role: Filter by role
            is_active: Filter by active status
            limit: Maximum users to return
            offset: Pagination offset

        Returns:
            List of users
        """
        query = select(User)

        if role is not None:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)

        query = query.order_by(User.created_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> int:
        """Count users with optional filtering.

        Args:
            role: Filter by role
            is_active: Filter by active status

        Returns:
            Count of users
        """
        from sqlalchemy import func

        query = select(func.count(User.id))

        if role is not None:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)

        result = await self.session.execute(query)
        return result.scalar_one()
