"""
Structured logging configuration.

Uses structlog to emit JSON logs with request-id correlation. Sensitive
values (passwords, tokens, API keys, raw farmer PII) must never be passed
into log calls -- see docs/SECURITY.md.
"""
import logging
import sys
import uuid
from contextvars import ContextVar

import structlog

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_REDACT_KEYS = {
    "password",
    "authorization",
    "access_token",
    "refresh_token",
    "api_key",
    "nvidia_api_key",
    "imd_api_key",
    "supabase_service_role_key",
    "jwt_secret_key",
}


def _redact_processor(logger, method_name, event_dict):
    for key in list(event_dict.keys()):
        if key.lower() in _REDACT_KEYS:
            event_dict[key] = "***redacted***"
    return event_dict


def _inject_request_id(logger, method_name, event_dict):
    event_dict["request_id"] = request_id_ctx.get()
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _inject_request_id,
            _redact_processor,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def get_logger(name: str = "bhoomi"):
    return structlog.get_logger(name)
