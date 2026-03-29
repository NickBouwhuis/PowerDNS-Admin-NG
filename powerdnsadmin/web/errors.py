"""
FastAPI exception handlers — JSON-only responses.

All error pages are rendered by the Next.js SPA. The backend only returns
JSON error responses.
"""
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPExceptions with JSON responses."""
    # Handle redirects
    if exc.status_code in (301, 302, 303, 307, 308):
        location = exc.headers.get("Location") if exc.headers else None
        if location:
            return RedirectResponse(url=location, status_code=exc.status_code)

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions with 500 JSON response."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register error handlers on the FastAPI app."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
