import time
import uuid

from fastapi import Request


async def request_logging_middleware(
    request: Request,
    call_next,
):
    """Attach a request ID and log API request timing."""

    request_id = request.headers.get(
        "X-Request-ID",
        str(uuid.uuid4()),
    )

    request.state.request_id = request_id

    logger = request.app.state.logger

    start = time.perf_counter()

    try:
        response = await call_next(request)

    except Exception:
        duration_ms = (
            time.perf_counter() - start
        ) * 1000

        logger.exception(
            "API request failed | "
            "request_id=%s method=%s path=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )

        raise

    duration_ms = (
        time.perf_counter() - start
    ) * 1000

    response.headers["X-Request-ID"] = request_id

    logger.info(
        "API request completed | "
        "request_id=%s method=%s path=%s "
        "status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )

    return response
