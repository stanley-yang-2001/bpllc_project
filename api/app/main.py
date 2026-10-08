from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import Settings, load_settings
from .db import make_pool
from .errors import install_error_handlers
from .migrate import run_migrations
from .routes import auth, health, me, words
from .security import LoginGuard, make_dummy_hash

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
PRIVATE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Vary": "Cookie",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
}
CSRF_HEADER, CSRF_VALUE = "x-requested-with", "tutor"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.run_migrations:
            run_migrations(settings.database_url)
        app.state.pool = make_pool(settings.database_url)
        yield
        app.state.pool.closeall()

    app = FastAPI(title="Language Tutor API", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.settings = settings
    app.state.login_guard = LoginGuard()
    app.state.dummy_hash = make_dummy_hash(settings.bcrypt_rounds)
    install_error_handlers(app)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        """Non-GET requests need the custom header, and a browser Origin (if sent) must be ours.
        Every response (errors included) is marked uncacheable: a shared browser or proxy must never be able
        to replay one person's JSON to another."""
        blocked = False
        if request.method not in SAFE_METHODS:
            origin = request.headers.get("origin")
            blocked = request.headers.get(CSRF_HEADER) != CSRF_VALUE or bool(origin and origin not in settings.allowed_origins)
        if blocked:
            response = JSONResponse({"error": {"code": "forbidden", "message": "Request blocked."}}, status_code=403)
        else:
            response = await call_next(request)
        for name, value in PRIVATE_HEADERS.items():
            response.headers[name] = value
        return response

    for module in (auth, me, words, health):
        app.include_router(module.router, prefix="/api")
    return app


def app_factory() -> FastAPI:        # uvicorn --factory app.main:app_factory
    return create_app()
