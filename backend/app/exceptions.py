"""Custom exceptions and error handlers for the application."""

from typing import Any


class AppException(Exception):
    """Base exception for application errors."""

    def __init__(
        self,
        message: str,
        code: str = "ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class UnauthorizedException(AppException):
    """User is not authenticated."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=401,
        )


class ForbiddenException(AppException):
    """User lacks permission for this action."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403,
        )


class NotFoundException(AppException):
    """Requested resource was not found."""

    def __init__(self, message: str = "Resource not found", resource: str | None = None):
        details = {"resource": resource} if resource else {}
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404,
            details=details,
        )


class ConflictException(AppException):
    """Resource conflict (e.g., duplicate)."""

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409,
        )


class ValidationException(AppException):
    """Request validation failed."""

    def __init__(self, message: str = "Validation failed", errors: list[dict] | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details={"errors": errors or []},
        )


class RateLimitedException(AppException):
    """Too many requests."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(
            message=message,
            code="RATE_LIMITED",
            status_code=429,
            details={"retry_after": retry_after},
        )


class ProcessingException(AppException):
    """Document or request processing failed."""

    def __init__(self, message: str = "Processing failed", document_id: str | None = None):
        details = {"document_id": document_id} if document_id else {}
        super().__init__(
            message=message,
            code="PROCESSING_ERROR",
            status_code=500,
            details=details,
        )


class LLMException(AppException):
    """LLM service error."""

    def __init__(self, message: str = "LLM service error", provider: str | None = None):
        details = {"provider": provider} if provider else {}
        super().__init__(
            message=message,
            code="LLM_ERROR",
            status_code=502,
            details=details,
        )


class ServiceUnavailableException(AppException):
    """External service is unavailable."""

    def __init__(self, message: str = "Service unavailable", service: str | None = None):
        details = {"service": service} if service else {}
        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            details=details,
        )
