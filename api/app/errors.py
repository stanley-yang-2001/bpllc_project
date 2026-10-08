"""One error body for every non-2xx response: {"error": {"code", "message", "retry_after", "details"}}."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("tutor.api")


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int, retry_after: int | None = None, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.retry_after, self.details = retry_after, details or {}


def validation_error(message: str, **details) -> AppError:
    return AppError("validation_error", message, 422, details=details)


def not_found(what: str = "Not found") -> AppError:
    return AppError("not_found", what, 404)


def conflict(message: str) -> AppError:
    return AppError("conflict", message, 409)


def unauthorized(message: str = "Please log in.") -> AppError:
    return AppError("unauthorized", message, 401)


def _body(code, message, retry_after=None, details=None):
    err = {"code": code, "message": message}
    if retry_after is not None:
        err["retry_after"] = retry_after
    if details:
        err["details"] = details
    return {"error": err}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        return JSONResponse(_body(exc.code, exc.message, exc.retry_after, exc.details), exc.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        msg = first.get("msg", "Invalid request").removeprefix("Value error, ")
        return JSONResponse(_body("validation_error", f"{loc}: {msg}" if loc else msg), 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 401: "unauthorized", 403: "forbidden", 405: "method_not_allowed"}.get(exc.status_code, "error")
        return JSONResponse(_body(code, str(exc.detail)), exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled error")
        return JSONResponse(_body("internal_error", "Something went wrong. Please try again."), 500)
