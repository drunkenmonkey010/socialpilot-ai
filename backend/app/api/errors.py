
import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


def _error_code(status_code: int) -> str:
    """Return a stable machine-readable code for an HTTP status."""

    codes = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }

    return codes.get(
        status_code,
        f"HTTP_{status_code}",
    )


def _message_from_detail(
    detail: Any,
    status_code: int,
) -> str:
    """
    Convert FastAPI HTTPException detail into a safe API message.

    Structured details can explicitly provide a code/message pair.
    String details are preserved because existing routes already use
    user-facing messages for expected application errors.
    """

    if isinstance(detail, dict):
        message = detail.get("message")

        if isinstance(message, str) and message.strip():
            return message

    if isinstance(detail, str) and detail.strip():
        return detail

    return _error_code(status_code).replace("_", " ").title()


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    """Return all HTTPException instances using the standard error format."""

    status_code = exc.status_code

    response = {
        "error": {
            "code": _error_code(status_code),
            "message": _message_from_detail(
                exc.detail,
                status_code,
            ),
        }
    }

    return JSONResponse(
        status_code=status_code,
        content=response,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return request validation failures using the standard error format."""

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": exc.errors(),
            }
        },
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Catch unexpected application errors without exposing internal details.
    """

    logger.exception(
        "Unhandled API exception",
        exc_info=exc,
        extra={
            "method": request.method,
            "path": request.url.path,
        },
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
            }
        },
    )
