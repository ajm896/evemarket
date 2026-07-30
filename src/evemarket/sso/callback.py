import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from evemarket.sso.config import CALLBACK_TIMEOUT, REDIRECT_URI

_PAGE = b"<!doctype html><title>evemarket</title><h1>Authorised.</h1><p>You can close this tab.</p>"


def make_callback_server(captured: dict[str, Any], expected_state: str) -> HTTPServer:
    """A bound, listening one-shot server for the SSO redirect URI.

    Returned already bound — the caller must create this *before* opening the
    browser, or a fast redirect can arrive before the socket exists. Supports
    the context-manager protocol (HTTPServer closes the socket on exit),
    matching make_client/make_connection's ownership contract.
    """
    redirect = urlsplit(REDIRECT_URI)
    callback_path = redirect.path
    host = redirect.hostname or "localhost"
    port = redirect.port or 80

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parts = urlsplit(self.path)
            if parts.path != callback_path:
                self.send_error(404)
                return

            query = parse_qs(parts.query)
            if "error" in query:
                captured["error"] = query.get("error_description", query["error"])[0]
                self.send_error(400, captured["error"])
                return
            if query.get("state", [""])[0] != expected_state:
                captured["error"] = "state mismatch"
                self.send_error(400, captured["error"])
                return

            captured["code"] = query["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            _ = self.wfile.write(_PAGE)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return HTTPServer((host, port), Handler)


def wait_for_callback(server: HTTPServer, captured: dict[str, Any]) -> str:
    """Serve requests until the SSO redirect arrives, then return its code.

    Blocking and synchronous — http.server has no async form. Call it via
    asyncio.to_thread so the event loop stays free.
    """
    server.timeout = 5
    deadline = time.monotonic() + CALLBACK_TIMEOUT
    while "code" not in captured and "error" not in captured and time.monotonic() < deadline:
        server.handle_request()
    if "error" in captured:
        raise RuntimeError(f"EVE SSO callback failed: {captured['error']}")
    if "code" not in captured:
        raise RuntimeError(f"No SSO callback received within {CALLBACK_TIMEOUT}s.")
    return captured["code"]
