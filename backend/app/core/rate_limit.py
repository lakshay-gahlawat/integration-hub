"""
Basic rate limiting middleware.

This is intentionally simple: a fixed-window counter per client IP, backed
by an in-process dict. It is enough to demonstrate the concept and to
protect the demo deployment; a production system handling real traffic
would move this to Redis (INCR + EXPIRE) so it works across multiple
backend replicas. The Redis-based version is sketched in the README's
"Future improvements" section.
"""
import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

_WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Don't rate-limit docs/openapi so the demo is easy to explore.
        if request.url.path in ("/docs", "/openapi.json", "/redoc", "/health"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - _WINDOW_SECONDS

        hits = self._hits[client_ip]
        hits[:] = [t for t in hits if t > window_start]

        if len(hits) >= settings.RATE_LIMIT_PER_MINUTE:
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limited", "message": "Too many requests, slow down."},
            )

        hits.append(now)
        return await call_next(request)
