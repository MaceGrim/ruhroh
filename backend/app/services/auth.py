"""Authentication service - Supabase integration."""

from uuid import UUID

import httpx
from jose import jwt, JWTError, ExpiredSignatureError
import structlog

from app.config import Settings

logger = structlog.get_logger()


class AuthError(Exception):
    """Authentication error."""

    pass


class AuthService:
    """Service for handling authentication via Supabase."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._http_client = None
        self._jwks = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30)
        return self._http_client

    async def _get_jwks(self) -> dict:
        """Fetch Supabase JWKS for token verification."""
        if self._jwks is None:
            client = await self._get_http_client()
            response = await client.get(
                f"{self.settings.supabase_url}/auth/v1/jwks"
            )
            response.raise_for_status()
            self._jwks = response.json()
        return self._jwks

    async def verify_token(self, token: str) -> UUID:
        """Verify JWT token and return user ID.

        Args:
            token: JWT token from Supabase

        Returns:
            User UUID from the token

        Raises:
            AuthError: If token is invalid or expired
        """
        try:
            # Get unverified header to find key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            # Get JWKS
            jwks = await self._get_jwks()

            # Find matching key
            rsa_key = None
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    rsa_key = key
                    break

            if rsa_key is None:
                # Fallback: try to decode without verification in dev mode
                if self.settings.debug:
                    payload = jwt.get_unverified_claims(token)
                    user_id = payload.get("sub")
                    if not user_id:
                        raise AuthError("Token missing user ID")
                    return UUID(user_id)
                raise AuthError("Unable to find appropriate key")

            # Verify token
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience="authenticated",
                issuer=f"{self.settings.supabase_url}/auth/v1",
            )

            user_id = payload.get("sub")
            if not user_id:
                raise AuthError("Token missing user ID")

            return UUID(user_id)

        except ExpiredSignatureError:
            raise AuthError("Token has expired")
        except JWTError as e:
            logger.warning("jwt_verification_failed", error=str(e))
            raise AuthError(f"Invalid token: {e}")
        except Exception as e:
            logger.error("auth_error", error=str(e))
            raise AuthError(f"Authentication failed: {e}")

    async def register_user(self, email: str, password: str) -> dict:
        """Register a new user via Supabase.

        Args:
            email: User email
            password: User password

        Returns:
            Dict with user_id and email

        Raises:
            AuthError: If registration fails
        """
        client = await self._get_http_client()

        try:
            response = await client.post(
                f"{self.settings.supabase_url}/auth/v1/signup",
                json={"email": email, "password": password},
                headers={
                    "apikey": self.settings.supabase_anon_key,
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 400:
                data = response.json()
                raise AuthError(data.get("msg", "Registration failed"))

            response.raise_for_status()
            data = response.json()

            user = data.get("user", {})
            return {
                "user_id": UUID(user["id"]),
                "email": user["email"],
            }

        except httpx.HTTPError as e:
            logger.error("supabase_register_error", error=str(e))
            raise AuthError(f"Registration failed: {e}")

    async def login_user(self, email: str, password: str) -> dict:
        """Login user via Supabase.

        Args:
            email: User email
            password: User password

        Returns:
            Dict with access_token, refresh_token, expires_in, user_id

        Raises:
            AuthError: If login fails
        """
        client = await self._get_http_client()

        try:
            response = await client.post(
                f"{self.settings.supabase_url}/auth/v1/token",
                params={"grant_type": "password"},
                json={"email": email, "password": password},
                headers={
                    "apikey": self.settings.supabase_anon_key,
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 400:
                data = response.json()
                raise AuthError(data.get("error_description", "Login failed"))

            response.raise_for_status()
            data = response.json()

            return {
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "expires_in": data["expires_in"],
                "user_id": UUID(data["user"]["id"]),
            }

        except httpx.HTTPError as e:
            logger.error("supabase_login_error", error=str(e))
            raise AuthError(f"Login failed: {e}")

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token.

        Args:
            refresh_token: Supabase refresh token

        Returns:
            Dict with new access_token and expires_in

        Raises:
            AuthError: If refresh fails
        """
        client = await self._get_http_client()

        try:
            response = await client.post(
                f"{self.settings.supabase_url}/auth/v1/token",
                params={"grant_type": "refresh_token"},
                json={"refresh_token": refresh_token},
                headers={
                    "apikey": self.settings.supabase_anon_key,
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 400:
                data = response.json()
                raise AuthError(data.get("error_description", "Token refresh failed"))

            response.raise_for_status()
            data = response.json()

            return {
                "access_token": data["access_token"],
                "expires_in": data["expires_in"],
            }

        except httpx.HTTPError as e:
            logger.error("supabase_refresh_error", error=str(e))
            raise AuthError(f"Token refresh failed: {e}")

    async def logout_user(self, token: str) -> None:
        """Logout user and invalidate session.

        Args:
            token: Current access token

        Raises:
            AuthError: If logout fails
        """
        client = await self._get_http_client()

        try:
            response = await client.post(
                f"{self.settings.supabase_url}/auth/v1/logout",
                headers={
                    "apikey": self.settings.supabase_anon_key,
                    "Authorization": f"Bearer {token}",
                },
            )
            response.raise_for_status()

        except httpx.HTTPError as e:
            logger.warning("supabase_logout_error", error=str(e))
            # Don't raise - logout is best effort

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
