"""FastAPI exception handlers for consistent error responses."""

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import (
    AppException,
    UnauthorizedException,
    ForbiddenException,
    NotFoundException,
    ConflictException,
    ValidationException,
    RateLimitedException,
    ProcessingException,
    LLMException,
    ServiceUnavailableException,
)

logger = structlog.get_logger()


def get_request_id(request: Request) -> str:
    """Get request ID from request state."""
    return getattr(request.state, "request_id", "unknown")


def create_error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict | None = None,
) -> JSONResponse:
    """Create consistent error response with request ID."""
    request_id = get_request_id(request)

    content = {
        "detail": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }

    if details:
        content["detail"].update(details)

    return JSONResponse(status_code=status_code, content=content)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions."""
    logger.error(
        "Application exception",
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        request_id=get_request_id(request),
    )

    response = create_error_response(
        request=request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details if exc.details else None,
    )

    # Add Retry-After header for rate limiting
    if isinstance(exc, RateLimitedException):
        response.headers["Retry-After"] = str(exc.details.get("retry_after", 60))

    return response


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Handle Starlette/FastAPI HTTP exceptions."""
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        request_id=get_request_id(request),
    )

    # Extract code and message from detail if it's a dict
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", "HTTP_ERROR")
        message = exc.detail.get("message", str(exc.detail))
    else:
        code = "HTTP_ERROR"
        message = str(exc.detail) if exc.detail else "An error occurred"

    return create_error_response(
        request=request,
        status_code=exc.status_code,
        code=code,
        message=message,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        loc = ".".join(str(l) for l in error["loc"])
        errors.append({
            "field": loc,
            "message": error["msg"],
            "type": error["type"],
        })

    logger.warning(
        "Validation error",
        errors=errors,
        request_id=get_request_id(request),
    )

    return create_error_response(
        request=request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": errors},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception(
        "Unexpected error",
        error=str(exc),
        error_type=type(exc).__name__,
        request_id=get_request_id(request),
    )

    return create_error_response(
        request=request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app."""
    # Custom application exceptions
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(UnauthorizedException, app_exception_handler)
    app.add_exception_handler(ForbiddenException, app_exception_handler)
    app.add_exception_handler(NotFoundException, app_exception_handler)
    app.add_exception_handler(ConflictException, app_exception_handler)
    app.add_exception_handler(ValidationException, app_exception_handler)
    app.add_exception_handler(RateLimitedException, app_exception_handler)
    app.add_exception_handler(ProcessingException, app_exception_handler)
    app.add_exception_handler(LLMException, app_exception_handler)
    app.add_exception_handler(ServiceUnavailableException, app_exception_handler)

    # Built-in exceptions
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
