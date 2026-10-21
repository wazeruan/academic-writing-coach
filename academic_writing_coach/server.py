"""Local HTTP server: serves the single-page app and a small JSON API. Standard library only."""

import json
import mimetypes
from datetime import date
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from . import llm, service
from .config import Settings
from .store import Store

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_BODY_BYTES = 512_000


class CoachHandler(BaseHTTPRequestHandler):
    server_version = "AcademicWritingCoach/0.1"

    def __init__(self, *args: Any, settings: Settings, store: Store, **kwargs: Any):
        self.settings = settings
        self.store = store
        super().__init__(*args, **kwargs)

    # Routing --------------------------------------------------------------
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send_file(STATIC_DIR / "index.html")
        elif path.startswith("/static/"):
            self._send_file(STATIC_DIR / path.removeprefix("/static/"))
        elif path == "/api/today":
            self._run(lambda: service.today(self.settings, self.store, date.today()))
        elif path == "/api/health":
            self._run(lambda: service.health(self.settings))
        elif path == "/api/learn":
            self._run(lambda: service.learn_overview(self.store))
        elif path == "/api/learn/unit":
            unit_id = parse_qs(urlsplit(self.path).query).get("id", [""])[0]
            self._run(lambda: service.unit_detail(self.store, unit_id))
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        routes = {
            "/api/draft": self._post_draft,
            "/api/submit": self._post_submit,
            "/api/level": self._post_level,
            "/api/practice/start": self._post_practice_start,
            "/api/practice/submit": self._post_practice_submit,
        }
        handler = routes.get(path)
        if handler is None:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            body = self._read_json()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self._run(lambda: handler(body))

    # Handlers -------------------------------------------------------------
    def _post_draft(self, body: dict[str, Any]) -> dict[str, Any]:
        return service.save_draft(self.store, date.today(), _text(body, "plan"), _text(body, "draft"))

    def _post_submit(self, body: dict[str, Any]) -> dict[str, Any]:
        return service.submit(
            self.settings, self.store, date.today(), _text(body, "plan"), _text(body, "draft")
        )

    def _post_level(self, body: dict[str, Any]) -> dict[str, Any]:
        return service.set_level(self.store, date.today(), _text(body, "level"))

    def _post_practice_start(self, body: dict[str, Any]) -> dict[str, Any]:
        return service.practice_start(self.settings, self.store, _text(body, "unit_id"))

    def _post_practice_submit(self, body: dict[str, Any]) -> dict[str, Any]:
        return service.practice_submit(
            self.settings,
            self.store,
            _text(body, "unit_id"),
            _text(body, "task"),
            _text(body, "plan"),
            _text(body, "draft"),
        )

    # Helpers --------------------------------------------------------------
    def _run(self, action: Any) -> None:
        try:
            result = action()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except llm.LLMError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
        except Exception as exc:  # Keep the server alive; report the failure to the page.
            self._send_json({"error": f"Unexpected error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
        else:
            self._send_json(result)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("Request body too large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Body must be JSON") from exc
        if not isinstance(body, dict):
            raise ValueError("Body must be a JSON object")
        return body

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, file_path: Path) -> None:
        resolved = file_path.resolve()
        if STATIC_DIR.resolve() not in resolved.parents or not resolved.is_file():
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        data = resolved.read_bytes()
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:  # Keep the terminal quiet.
        return


def _text(body: dict[str, Any], key: str) -> str:
    value = body.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"'{key}' must be a string")
    return value


def make_server(settings: Settings, store: Store | None = None) -> ThreadingHTTPServer:
    store = store or Store(settings.db_path)
    handler = partial(CoachHandler, settings=settings, store=store)
    return ThreadingHTTPServer((settings.host, settings.port), handler)


def main() -> None:
    settings = llm.resolve_model(Settings())
    server = make_server(settings)
    print(f"Academic Writing Coach running at http://{settings.host}:{settings.port}")
    print(f"Local LLM expected at {settings.llm_base_url} (model: {settings.llm_model})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
