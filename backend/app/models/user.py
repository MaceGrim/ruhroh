"""User Pydantic models."""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.common import BaseSchema


class UserBase(BaseModel):
    """Base user fields."""

    email: EmailStr = Field(..., description="User email address")


class UserCreate(UserBase):
    """Schema for user registration request."""

    password: str = Field(
        ...,
        min_length=8,
        description="Password (minimum 8 characters)",
    )


class UserLogin(UserBase):
    """Schema for user login request."""

    password: str = Field(..., description="User password")


class UserResponse(BaseSchema):
    """Schema for user in API responses."""

    id: UUID
    email: str
    role: Literal["user", "superuser", "admin"]
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool


class UserUpdate(BaseModel):
    """Schema for updating user (admin only)."""

    role: Optional[Literal["user", "superuser", "admin"]] = None
    is_active: Optional[bool] = None


class AuthTokenResponse(BaseModel):
    """Schema for authentication token response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str = Field(..., description="Refresh token")


class TokenRefreshResponse(BaseModel):
    """Schema for token refresh response."""

    access_token: str = Field(..., description="New JWT access token")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class UserRegisterResponse(BaseModel):
    """Schema for user registration response."""

    user_id: UUID
    email: str
