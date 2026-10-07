"""Small, synchronous reverse proxy for trusted local clients.

It hides the upstream credential and intentionally leaves retries, streaming,
and persistence to a separately reviewed gateway.
"""
from __future__ import annotations

import hmac
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_BODY_BYTES = 2_000_000
MAX_RESPONSE_BYTES = 20_000_000
ALLOWED_PATHS = frozenset({"/responses", "/chat/completions", "/images/generations", "/images/edits"})
DEFAULT_UPSTREAM = "https://argolink.io/v1"


def load_aliases(raw: str) -> dict[str, str]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("MODEL_ALIASES must be a JSON object") from exc
    if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()):
        raise ValueError("MODEL_ALIASES must map string aliases to string model IDs")
    return value


def rewrite_payload(raw: bytes, aliases: dict[str, str]) -> bytes:
    """Validate a JSON request and rewrite only an explicitly configured model alias."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("request body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    model = payload.get("model")
    if model is not None and not isinstance(model, str):
        raise ValueError("model must be a string")
    if model in aliases:
        payload["model"] = aliases[model]
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def build_request(path: str, body: bytes, base_url: str, api_key: str) -> Request:
    return Request(
        base_url.rstrip("/") + path,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ai-proxy-workflow/1.0",
            "Content-Length": str(len(body)),
        },
    )


def _safe_int(value: str | None) -> int | None:
    try:
        number = int(value or "")
    except ValueError:
        return None
    return number if number >= 0 else None


class ProxyHandler(BaseHTTPRequestHandler):
    server_version = "ai-proxy-workflow/1.0"

    def _json_error(self, status: int, message: str) -> None:
        body = json.dumps({"error": {"message": message, "type": "proxy_error"}}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _client_authorized(self) -> bool:
        expected = os.getenv("PROXY_API_KEY")
        if not expected:
            return True  # loopback-only deployments can intentionally omit a second key
        supplied = self.headers.get("Authorization", "")
        if not supplied.startswith("Bearer "):
            return False
        return hmac.compare_digest(supplied[7:], expected)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path not in ALLOWED_PATHS:
            self._json_error(HTTPStatus.NOT_FOUND, "path is not enabled by this proxy")
            return
        if not self._client_authorized():
            self._json_error(HTTPStatus.UNAUTHORIZED, "proxy authentication failed")
            return
        length = _safe_int(self.headers.get("Content-Length"))
        if length is None:
            self._json_error(HTTPStatus.LENGTH_REQUIRED, "Content-Length is required")
            return
        if length > MAX_BODY_BYTES:
            self._json_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body exceeds the 2 MB limit")
            return
        raw = self.rfile.read(length)
        if len(raw) != length:
            self._json_error(HTTPStatus.BAD_REQUEST, "request body was truncated")
            return
        try:
            body = rewrite_payload(raw, load_aliases(os.getenv("MODEL_ALIASES", "")))
            request = build_request(self.path, body, os.getenv("UPSTREAM_BASE_URL", DEFAULT_UPSTREAM), os.environ["UPSTREAM_API_KEY"])
        except KeyError:
            self._json_error(HTTPStatus.INTERNAL_SERVER_ERROR, "upstream credential is not configured")
            return
        except ValueError as exc:
            self._json_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        try:
            with urlopen(request, timeout=float(os.getenv("UPSTREAM_TIMEOUT", "90"))) as response:
                output = response.read(MAX_RESPONSE_BYTES + 1)
                status = response.status
                content_type = response.headers.get("Content-Type", "application/json")
                request_id = response.headers.get("x-request-id")
                retry_after = response.headers.get("Retry-After")
        except HTTPError as exc:
            output = exc.read(MAX_RESPONSE_BYTES + 1)
            status = exc.code
            content_type = exc.headers.get("Content-Type", "application/json")
            request_id = exc.headers.get("x-request-id")
            retry_after = exc.headers.get("Retry-After")
        except (TimeoutError, URLError, OSError):
            self._json_error(HTTPStatus.BAD_GATEWAY, "upstream transport failed")
            return
        if len(output) > MAX_RESPONSE_BYTES:
            self._json_error(HTTPStatus.BAD_GATEWAY, "upstream response exceeds the 20 MB limit")
            return
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(output)))
        if request_id:
            self.send_header("X-Upstream-Request-Id", request_id)
        if retry_after:
            self.send_header("Retry-After", retry_after)
        self.end_headers()
        self.wfile.write(output)

    def log_message(self, *_args: object) -> None:
        return


def main() -> None:
    host = os.getenv("LISTEN_HOST", "127.0.0.1")
    port = int(os.getenv("LISTEN_PORT", "8080"))
    ThreadingHTTPServer((host, port), ProxyHandler).serve_forever()


if __name__ == "__main__":
    main()
