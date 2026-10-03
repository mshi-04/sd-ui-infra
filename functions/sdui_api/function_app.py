import logging

import azure.functions as func

from auth import AuthError, extract_bearer_token, jwks_key_resolver, verify_token
from dependency_errors import DependencyError, DependencyUnavailableError
from response import cache_headers, error_response, json_response, not_modified
from settings import SettingsError, load_settings
from ui_repository import fetch_latest_definition, fetch_profile
from ui_resolver import etag_of, resolve

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
logger = logging.getLogger(__name__)


@app.route(route="ui/{surface}", methods=["GET"])
def get_ui_schema(req: func.HttpRequest) -> func.HttpResponse:
    surface = req.route_params.get("surface", "")

    try:
        return _serve(req, surface)
    except SettingsError as error:
        logger.error("settings unavailable surface=%s variable=%s problem=%s", surface, error.variable, error.problem)
        return error_response(500, "internal_error")
    except DependencyUnavailableError as error:
        logger.warning("dependency unavailable surface=%s dependency=%s detail=%s", surface, error.dependency, error.detail)
        return error_response(503, "service_unavailable")
    except DependencyError as error:
        logger.error("dependency failed surface=%s dependency=%s detail=%s", surface, error.dependency, error.detail)
        return error_response(500, "internal_error")
    except Exception:
        logger.exception("unexpected ui request failure surface=%s", surface)
        return error_response(500, "internal_error")


def _serve(req: func.HttpRequest, surface: str) -> func.HttpResponse:
    settings = load_settings()

    try:
        token = extract_bearer_token(req.headers.get("Authorization"))
        principal = verify_token(
            token,
            key_resolver=jwks_key_resolver(settings.jwks_uri),
            issuer=settings.issuer,
            audience=settings.api_client_id,
            required_scope=settings.required_scope,
        )
    except AuthError as error:
        logger.info("rejected ui request surface=%s reason=%s", surface, error.reason)
        return error_response(401, "unauthorized")

    definition = fetch_latest_definition(settings, surface)
    if definition is None:
        return error_response(404, "surface_not_found")

    resolved = resolve(definition, fetch_profile(settings, principal.subject), principal, settings.role_entitlements)
    etag = etag_of(resolved)

    if req.headers.get("If-None-Match") == etag:
        return not_modified(etag, settings.cache_max_age_seconds)

    logger.info(
        "resolved ui surface=%s subject=%s revision=%s components=%d",
        surface,
        principal.masked_subject,
        resolved.revision,
        len(resolved.components),
    )
    return json_response(200, resolved.to_payload(), cache_headers(etag, settings.cache_max_age_seconds))
