import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import get_logger, new_request_id, request_id_ctx

logger = get_logger("bhoomi.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id") or new_request_id()
        token = request_id_ctx.set(req_id)
        start = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        duration_ms = int((time.monotonic() - start) * 1000)
        response.headers["x-request-id"] = req_id
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=getattr(response, "status_code", None),
            duration_ms=duration_ms,
        )
        return response


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
        return response
