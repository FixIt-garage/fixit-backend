import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.errors import ErrorDetail, ErrorResponse, LegacyValidationError

logger = logging.getLogger(__name__)

HTTP_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "unprocessable_entity",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
    legacy_detail: str | list[LegacyValidationError] | None = None,
) -> JSONResponse:
    body = ErrorResponse(code=code, message=message, details=details or [], detail=legacy_detail)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json", exclude_none=True),
        headers=headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        ErrorDetail(
            field=".".join(str(part) for part in error["loc"]),
            message=error["msg"],
        )
        for error in exc.errors()
    ]
    # Old format for clients that still read detail[].loc. No "input": it may hold a password.
    legacy = [
        LegacyValidationError(loc=list(error["loc"]), msg=error["msg"], type=error["type"])
        for error in exc.errors()
    ]
    return error_response(
        422, "validation_error", "Request validation failed", details, legacy_detail=legacy
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = HTTP_ERROR_CODES.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return error_response(
        exc.status_code, code, message, headers=exc.headers, legacy_detail=message
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response(500, "internal_error", "Internal server error")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)