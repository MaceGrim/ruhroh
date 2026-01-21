"""FastAPI dependency injection."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.database import get_db_session
from app.db.repositories.user import UserRepository
from app.db.models import User
from app.services.auth import AuthService

# Dev mode user ID (used when DEV_MODE=true)
DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


async def get_auth_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    """Get auth service dependency."""
    return AuthService(settings)


async def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
    auth_service: Annotated[AuthService, Depends(get_auth_service)] = None,
) -> UUID:
    """Extract and validate user ID from JWT token."""
    # Dev mode: bypass auth
    if settings and settings.dev_mode:
        return DEV_USER_ID

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Missing or invalid authorization header",
            },
        )

    token = authorization.removeprefix("Bearer ")

    try:
        user_id = await auth_service.verify_token(token)
        return user_id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": str(e),
            },
        )


async def get_current_user(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> User:
    """Get current user from database."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    # Dev mode: create dev user if not exists
    if not user and settings and settings.dev_mode and user_id == DEV_USER_ID:
        user = await user_repo.create(
            user_id=DEV_USER_ID,
            email="dev@localhost",
            role="admin",  # Admin for full access in dev mode
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "User not found",
            },
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "User account is deactivated",
            },
        )

    return user


def require_role(allowed_roles: list[str]):
    """Dependency factory for role-based access control."""

    async def check_role(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": "Insufficient permissions",
                },
            )
        return user

    return check_role


# Common role dependencies
require_user = require_role(["user", "superuser", "admin"])
require_superuser = require_role(["superuser", "admin"])
require_admin = require_role(["admin"])
