import json
from collections.abc import Mapping

import azure.functions as func

CONTENT_TYPE = "application/json"


def json_response(status_code: int, body: Mapping[str, object], headers: dict[str, str] | None = None) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(body, ensure_ascii=False, separators=(",", ":")),
        status_code=status_code,
        mimetype=CONTENT_TYPE,
        headers=headers or {},
    )


def not_modified(etag: str, max_age_seconds: int) -> func.HttpResponse:
    return func.HttpResponse(
        status_code=304,
        headers=cache_headers(etag, max_age_seconds),
    )


def error_response(status_code: int, code: str) -> func.HttpResponse:
    return json_response(status_code, {"error": {"code": code}})


def cache_headers(etag: str, max_age_seconds: int) -> dict[str, str]:
    return {
        "ETag": etag,
        "Cache-Control": f"private, max-age={max_age_seconds}",
        "Vary": "Authorization",
    }
