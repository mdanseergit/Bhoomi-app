"""
Domain exceptions and the central exception -> HTTP response mapping.

Raw internal errors (stack traces, DB errors, provider connection errors)
must never be surfaced to the client. Every exception here carries a
user-safe message.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse


class BhoomiError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    user_message = "The request could not be completed."
    code = "BHOOMI_ERROR"

    def __init__(self, user_message: str | None = None, log_context: dict | None = None):
        self.user_message = user_message or self.user_message
        self.log_context = log_context or {}
        super().__init__(self.user_message)


class NotFoundError(BhoomiError):
    status_code = status.HTTP_404_NOT_FOUND
    user_message = "The requested resource was not found."
    code = "NOT_FOUND"


class ValidationFailedError(BhoomiError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    user_message = "The submitted data is invalid."
    code = "VALIDATION_FAILED"


class UnauthorizedError(BhoomiError):
    status_code = status.HTTP_401_UNAUTHORIZED
    user_message = "Authentication is required."
    code = "UNAUTHORIZED"


class ForbiddenError(BhoomiError):
    status_code = status.HTTP_403_FORBIDDEN
    user_message = "You do not have permission to perform this action."
    code = "FORBIDDEN"


class ConflictError(BhoomiError):
    status_code = status.HTTP_409_CONFLICT
    user_message = "This action conflicts with the current state of the resource."
    code = "CONFLICT"


class RateLimitedError(BhoomiError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    user_message = "Too many requests. Please slow down and try again shortly."
    code = "RATE_LIMITED"


class ProviderUnavailableError(BhoomiError):
    """Raised when an external provider (weather, satellite, AI) fails.

    Callers should catch this and fall back to cached data or deterministic
    logic rather than letting it bubble up as a hard failure whenever a
    graceful degradation path exists.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    user_message = "This data source is temporarily unavailable. Showing the most recent verified information."
    code = "PROVIDER_UNAVAILABLE"


async def bhoomi_exception_handler(request: Request, exc: BhoomiError) -> JSONResponse:
    from app.core.logging import get_logger

    logger = get_logger("bhoomi.error")
    logger.warning("handled_error", code=exc.code, path=str(request.url.path), **exc.log_context)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.user_message}},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    from app.core.logging import get_logger

    logger = get_logger("bhoomi.error")
    logger.error("unhandled_error", path=str(request.url.path), error=repr(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Something went wrong on our side. Our team has been notified.",
            }
        },
    )
