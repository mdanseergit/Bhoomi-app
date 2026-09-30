from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.exceptions import BhoomiError, bhoomi_exception_handler, unhandled_exception_handler
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware

configure_logging(settings.LOG_LEVEL)

# Refuse to boot with an unsafe or incomplete configuration rather than
# serving traffic that silently behaves incorrectly.
_CONFIG_PROBLEMS = settings.validate_for_startup()
if _CONFIG_PROBLEMS:
    raise RuntimeError(
        "BHOOMI cannot start with the current configuration:\n  - "
        + "\n  - ".join(_CONFIG_PROBLEMS)
    )

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description=(
        "BHOOMI Agriculture Intelligence Platform API -- farm intelligence, "
        "crop disease analysis, and the state cooperation network."
    ),
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)

app.add_exception_handler(BhoomiError, bhoomi_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root():
    return {"service": settings.APP_NAME, "status": "running", "docs": "/api/docs"}
