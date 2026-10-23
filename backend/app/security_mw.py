"""Security middleware: strict headers, Redis fixed-window rate limiting, body-size cap, login lockout."""
import time
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

HEADERS = {
    "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}

class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        r = await call_next(request)
        if not request.url.path.startswith(("/docs", "/openapi")):
            r.headers.update(HEADERS)
        return r

class BodyLimit(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int = 2_000_000):
        super().__init__(app); self.max = max_bytes
    async def dispatch(self, request: Request, call_next):
        if int(request.headers.get("content-length", 0)) > self.max:
            return JSONResponse({"detail": "Payload too large"}, 413)
        return await call_next(request)

class RateLimit(BaseHTTPMiddleware):
    """Per-IP fixed window. Stricter on /auth. Fails open if Redis is down (log + alert in prod)."""
    def __init__(self, app, per_min: int = 120, auth_per_min: int = 10):
        super().__init__(app); self.per_min, self.auth_per_min = per_min, auth_per_min
    async def dispatch(self, request: Request, call_next):
        r = getattr(request.app.state, "redis", None)
        if r is not None:
            ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
            auth = request.url.path.startswith("/auth")
            key = f"rl:{'auth' if auth else 'api'}:{ip}:{int(time.time() // 60)}"
            try:
                n = await r.incr(key)
                if n == 1: await r.expire(key, 70)
                if n > (self.auth_per_min if auth else self.per_min):
                    return JSONResponse({"detail": "Rate limit exceeded"}, 429, headers={"Retry-After": "60"})
            except Exception:
                pass
        return await call_next(request)

async def login_locked(redis, email: str, limit: int = 5, window: int = 900) -> bool:
    return int(await redis.get(f"lock:{email}") or 0) >= limit

async def login_failed(redis, email: str, window: int = 900):
    k = f"lock:{email}"; await redis.incr(k); await redis.expire(k, window)
