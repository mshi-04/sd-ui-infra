import argparse
import json
import sys
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "functions" / "sdui_api"))

from auth import Principal
from models import AccountProfile, ResolvedUiPayload, UiDefinition
from ui_resolver import etag_of, resolve

SEED_ROOT = REPOSITORY_ROOT / "seed"
APP_ROLES_PATH = REPOSITORY_ROOT / "config" / "app_roles.json"
ROUTE_PREFIX = "/api/ui/"
OID_HEADER = "X-Dev-Oid"
ROLES_HEADER = "X-Dev-Roles"
CACHE_MAX_AGE_SECONDS = 60


def load_definitions() -> dict[str, UiDefinition]:
    definitions: dict[str, UiDefinition] = {}
    first_file_by_version: dict[tuple[str, str], str] = {}
    for path in sorted((SEED_ROOT / "ui_definitions").glob("*.json")):
        definition = UiDefinition.from_document(json.loads(path.read_text(encoding="utf-8")))
        file = path.relative_to(SEED_ROOT.parent).as_posix()
        key = (definition.surface, definition.version)
        first_file = first_file_by_version.get(key)
        if first_file is not None:
            raise ValueError(f"{file}: $.version: duplicates surface and version from {first_file}")
        first_file_by_version[key] = file

        current = definitions.get(definition.surface)
        if current is None or definition.version > current.version:
            definitions[definition.surface] = definition
    return definitions


def load_profiles() -> dict[str, AccountProfile]:
    profiles = {}
    for path in sorted((SEED_ROOT / "account_profiles").glob("*.json")):
        profile = AccountProfile.from_document(json.loads(path.read_text(encoding="utf-8")))
        profiles[profile.user_id] = profile
    return profiles


def load_role_entitlements() -> dict[str, frozenset[str]]:
    roles = json.loads(APP_ROLES_PATH.read_text(encoding="utf-8"))
    return {name: frozenset(role["entitlements"]) for name, role in roles.items()}


def resolve_payload(surface: str, oid: str, roles: frozenset[str]) -> tuple[ResolvedUiPayload, str] | None:
    definition = load_definitions().get(surface)
    if definition is None:
        return None

    profile = load_profiles().get(oid, AccountProfile.empty(oid))
    resolved = resolve(definition, profile, Principal(subject=oid, app_roles=roles), load_role_entitlements())
    return resolved.to_payload(), etag_of(resolved)


def parse_roles(header_value: str | None) -> frozenset[str]:
    if not header_value:
        return frozenset()
    return frozenset(role.strip() for role in header_value.split(",") if role.strip())


class UiSchemaHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        if not self.path.startswith(ROUTE_PREFIX):
            self._send_json(404, {"error": {"code": "not_found"}})
            return

        surface = self.path[len(ROUTE_PREFIX) :].split("?")[0]
        oid = self.headers.get(OID_HEADER, "anonymous")
        resolution = resolve_payload(surface, oid, parse_roles(self.headers.get(ROLES_HEADER)))

        if resolution is None:
            self._send_json(404, {"error": {"code": "surface_not_found"}})
            return

        payload, etag = resolution
        if self.headers.get("If-None-Match") == etag:
            self._send_headers(304, 0, etag)
            return

        self._send_json(200, payload, etag)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(f"{self.address_string()} {format % args}\n")

    def _send_json(self, status_code: int, payload: Mapping[str, object], etag: str | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._send_headers(status_code, len(body), etag)
        self.wfile.write(body)

    def _send_headers(self, status_code: int, content_length: int, etag: str | None) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(content_length))
        if etag:
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", f"private, max-age={CACHE_MAX_AGE_SECONDS}")
        self.end_headers()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve seed UI schemas without Azure. Development use only")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    arguments = parser.parse_args()

    print(f"serving seed UI schemas on http://{arguments.host}:{arguments.port}{ROUTE_PREFIX}<surface>")
    print(f"identity comes from {OID_HEADER} and {ROLES_HEADER}; no token is verified")
    ThreadingHTTPServer((arguments.host, arguments.port), UiSchemaHandler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
