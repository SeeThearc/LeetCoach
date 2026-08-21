"""Custom exception classes and global exception handlers.

Why custom exceptions instead of raising HTTPException everywhere?
- Separation of concerns: service/repository layers shouldn't know about HTTP
- Consistent error responses: all errors follow the same JSON structure
- Centralized handling: one place to control error logging and formatting
- Testability: services raise domain exceptions; tests don't need HTTP context

The pattern:
  Service raises AppError → FastAPI handler catches it → Returns JSON response

This follows Clean Architecture: inner layers (services) don't depend on
outer layers (HTTP framework).
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Custom Exception Hierarchy
# ---------------------------------------------------------------------------

class AppError(Exception):
    """Base exception for all application-level errors.

    All custom exceptions inherit from this, so we can catch
    'any application error' with a single except clause.

    Attributes:
        message: Human-readable error description.
        error_code: Machine-readable error code for the client.
        status_code: HTTP status code to return.
    """

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(AppError):
    """Resource was not found."""

    def __init__(self, resource: str = "Resource", identifier: str = ""):
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} '{identifier}' not found"
        super().__init__(
            message=detail,
            error_code="NOT_FOUND",
            status_code=404,
        )


class ValidationError(AppError):
    """Business logic validation failed."""

    def __init__(self, message: str = "Validation failed"):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
        )


class ExternalServiceError(AppError):
    """An external service (LeetCode API, Gemini) failed."""

    def __init__(self, service: str, message: str = "Service unavailable"):
        super().__init__(
            message=f"{service}: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
        )


class AIError(AppError):
    """AI/LLM processing error."""

    def __init__(self, message: str = "AI processing failed"):
        super().__init__(
            message=message,
            error_code="AI_ERROR",
            status_code=500,
        )


# ---------------------------------------------------------------------------
# Global Exception Handlers
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app.

    These handlers ensure ALL errors return a consistent JSON structure:
    {
        "error_code": "MACHINE_READABLE_CODE",
        "message": "Human-readable description",
        "details": null | [...]
    }

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Handle all custom application errors."""
        log_level = "warning" if exc.status_code < 500 else "error"
        getattr(logger, log_level)(
            "Application error",
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            path=str(request.url),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "details": None,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic request validation errors."""
        logger.warning(
            "Request validation failed",
            path=str(request.url),
            errors=exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "VALIDATION_ERROR",
                "message": "Invalid request data",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Handle standard HTTP exceptions (404, 405, etc.)."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": "HTTP_ERROR",
                "message": str(exc.detail),
                "details": None,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all for unhandled exceptions.

        CRITICAL: Never leak internal error details to clients.
        Log the full exception for debugging, but return a generic message.
        """
        logger.error(
            "Unhandled exception",
            error_type=type(exc).__name__,
            error=str(exc),
            path=str(request.url),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": None,
            },
        )
