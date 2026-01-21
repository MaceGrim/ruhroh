"""Rate limiting middleware using sliding window algorithm."""

import time
from collections import defaultdict
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.config import Settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter with per-user/IP tracking."""

    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.requests_per_minute = settings.rate_limit_rpm
        self.burst_limit = settings.rate_limit_burst
        self.window_size = 60  # 1 minute in seconds

        # In-memory storage: key -> list of timestamps
        # In production, use Redis for distributed rate limiting
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_key(self, request: Request) -> str:
        """Get rate limit key from user ID or IP address."""
        # Try to get user ID from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"ip:{client_ip}"

    def _cleanup_old_requests(self, key: str, now: float) -> None:
        """Remove requests older than the window."""
        cutoff = now - self.window_size
        self._requests[key] = [
            ts for ts in self._requests[key] if ts > cutoff
        ]

    def _check_rate_limit(self, key: str) -> tuple[bool, int, int, int]:
        """
        Check if request is within rate limits.

        Returns:
            (allowed, limit, remaining, reset_time)
        """
        now = time.time()

        # Clean up old requests
        self._cleanup_old_requests(key, now)

        request_count = len(self._requests[key])

        # Calculate remaining requests and reset time
        remaining = max(0, self.requests_per_minute - request_count)
        reset_time = int(now) + self.window_size

        # Check burst limit (requests in last second)
        recent_second = [ts for ts in self._requests[key] if ts > now - 1]
        if len(recent_second) >= self.burst_limit:
            return False, self.requests_per_minute, remaining, reset_time

        # Check requests per minute
        if request_count >= self.requests_per_minute:
            return False, self.requests_per_minute, 0, reset_time

        # Record this request
        self._requests[key].append(now)

        return True, self.requests_per_minute, remaining - 1, reset_time

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Check rate limits and process request."""
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/api/v1/admin/health"]:
            return await call_next(request)

        key = self._get_client_key(request)
        allowed, limit, remaining, reset_time = self._check_rate_limit(key)

        if not allowed:
            retry_after = reset_time - int(time.time())
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please try again later.",
                    }
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(retry_after),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to all responses
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response
