"""
FastAPI middleware stack for the web application.

Includes:
- SecurityHeadersMiddleware: HSTS, X-Frame-Options, etc.
- MaintenanceModeMiddleware: Returns 503 when maintenance mode is active
- Server-side session middleware
"""
import logging

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    def __init__(self, app, hsts_enabled: bool = False):
        super().__init__(app)
        self.hsts_enabled = hsts_enabled

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if self.hsts_enabled:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    """Return 503 for all requests when maintenance mode is active.

    Exempt paths: /api/ (API has its own auth).
    """

    EXEMPT_PREFIXES = ("/api/",)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        for prefix in self.EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        try:
            from powerdnsadmin.models.setting import Setting
            if Setting().get('maintenance'):
                return JSONResponse(
                    status_code=503,
                    content={"detail": "The system is currently under maintenance. Please try again later."},
                )
        except Exception:
            pass

        return await call_next(request)


DEFAULT_SESSION_TIMEOUT = 10


def setup_middleware(app: FastAPI, config: dict) -> None:
    """Configure all middleware on the FastAPI app.

    Order matters — middleware is applied in reverse order of registration
    (last registered = outermost = runs first).
    """
    from powerdnsadmin.web.session import ServerSideSessionMiddleware

    # Rate limiting via slowapi (if available)
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded

        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    except ImportError:
        logger.info("slowapi not installed, rate limiting disabled")

    # Security headers (outermost — added to every response)
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts_enabled=config.get('HSTS_ENABLED', False),
    )

    # Maintenance mode
    app.add_middleware(MaintenanceModeMiddleware)

    # Server-side sessions (innermost of custom middleware)
    app.add_middleware(
        ServerSideSessionMiddleware,
        secret_key=config.get('SECRET_KEY', ''),
        session_timeout_minutes=config.get('SESSION_TIMEOUT', DEFAULT_SESSION_TIMEOUT),
        cookie_httponly=config.get('CSRF_COOKIE_HTTPONLY', True),
        cookie_samesite=config.get('SESSION_COOKIE_SAMESITE', 'Lax'),
        cookie_secure=config.get('SESSION_COOKIE_SECURE', False),
    )
