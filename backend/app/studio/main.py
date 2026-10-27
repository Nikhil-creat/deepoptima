"""DeepOptima Studio: FastAPI application (API + optional static frontend)."""
import asyncio, logging, os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from . import VERSION, runner
from .db import init_db
from .routes_auth import router as auth_router
from .routes_data import router as data_router
from .routes_keys import router as keys_router
from .routes_misc import router as misc_router
from .settings import settings

log = logging.getLogger("studio")
PAGE_CSP = ("default-src 'self'; media-src 'self' https://d8j0ntlcm91z4.cloudfront.net; connect-src 'self' https: http://localhost:* http://127.0.0.1:*; "
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await runner.recover()
    task = asyncio.create_task(runner.retention_loop()) if settings.retention_days > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="DeepOptima Studio", version=VERSION, lifespan=lifespan, docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"], max_age=600)


class Hardening(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        big_ok = request.url.path.endswith(("/datasets", "/predict-file"))
        cap = (settings.max_upload_mb + 1) * 1024 * 1024 if big_ok else 1024 * 1024
        if cl and cl.isdigit() and int(cl) > cap:
            return JSONResponse({"detail": "Request body too large."}, status_code=413)
        resp = await call_next(request)
        h = resp.headers
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "no-referrer"
        h["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
        h["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        if request.url.path.startswith("/api"):
            h["Cache-Control"] = "no-store"
            if "/api/docs" not in request.url.path and "openapi" not in request.url.path:
                h["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        else:
            h["Content-Security-Policy"] = PAGE_CSP
        return resp


app.add_middleware(Hardening)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse({"detail": "Unexpected server error. Please try again."}, status_code=500)


for r in (auth_router, data_router, keys_router, misc_router):
    app.include_router(r)

if settings.static_dir and os.path.isdir(settings.static_dir):
    app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="web")
