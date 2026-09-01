"""
Phase 22 HTTP Security Headers Middleware.

Injects defense-in-depth HTTP security headers into all responses:
 - Content-Security-Policy (CSP)
 - X-Content-Type-Options: nosniff
 - X-Frame-Options: DENY (Anti-Clickjacking)
 - Referrer-Policy: strict-origin-when-cross-origin
 - Permissions-Policy
 - Strict-Transport-Security (HSTS in production)
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # Standard anti-MIME-sniffing & anti-clickjacking
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"

        # Content-Security-Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss: http: https:; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp

        # HSTS in production
        if getattr(settings, "ENVIRONMENT", "development") == "production" or getattr(settings, "APP_ENV", "") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        return response
