"""Authentication API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.database import get_db_session
from app.db.repositories.user import UserRepository
from app.models import (
    UserCreate,
    UserLogin,
    UserRegisterResponse,
    AuthTokenResponse,
    RefreshTokenRequest,
    TokenRefreshResponse,
    ErrorResponse,
)
from app.services.auth import AuthService, AuthError

router = APIRouter()


async def get_auth_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    """Get auth service dependency."""
    return AuthService(settings)


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}},
)
async def register(
    data: UserCreate,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Register a new user.

    Creates user in Supabase Auth and stores metadata in local database.
    """
    try:
        # Register with Supabase
        result = await auth_service.register_user(data.email, data.password)

        # Create user record in local DB
        user_repo = UserRepository(db)
        existing = await user_repo.get_by_email(data.email)

        if not existing:
            await user_repo.create(
                user_id=result["user_id"],
                email=data.email,
            )

        return UserRegisterResponse(
            user_id=result["user_id"],
            email=result["email"],
        )

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REGISTRATION_FAILED", "message": str(e)},
        )


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    responses={401: {"model": ErrorResponse}},
)
async def login(
    data: UserLogin,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Login user and return tokens.

    Authenticates with Supabase and updates last login timestamp.
    """
    try:
        result = await auth_service.login_user(data.email, data.password)

        # Update last login
        user_repo = UserRepository(db)
        user = await user_repo.get_by_email(data.email)

        if user:
            await user_repo.update_last_login(user.id)
        else:
            # Create user if not exists (first login after Supabase signup)
            await user_repo.create(
                user_id=result["user_id"],
                email=data.email,
            )

        return AuthTokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_in=result["expires_in"],
        )

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "LOGIN_FAILED", "message": str(e)},
        )


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    responses={401: {"model": ErrorResponse}},
)
async def refresh_token(
    data: RefreshTokenRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Refresh access token.

    Uses Supabase refresh token to get a new access token.
    """
    try:
        result = await auth_service.refresh_token(data.refresh_token)

        return TokenRefreshResponse(
            access_token=result["access_token"],
            expires_in=result["expires_in"],
        )

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "REFRESH_FAILED", "message": str(e)},
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    authorization: Annotated[str | None, Header()] = None,
    auth_service: Annotated[AuthService, Depends(get_auth_service)] = None,
):
    """Logout user and invalidate session.

    Calls Supabase to invalidate the session.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")
        await auth_service.logout_user(token)

    return None
