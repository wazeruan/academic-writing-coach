"""Shared fixtures: a fake OpenAI-compatible LLM server, settings on tmp_path, and a store."""

import json
import socket
import sys
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from academic_writing_coach import llm  # noqa: E402
from academic_writing_coach.config import Settings  # noqa: E402
from academic_writing_coach.store import Store  # noqa: E402

DAY = date(2026, 10, 20)


class FakeLLM:
    """Minimal /v1/chat/completions stand-in. Replies are consumed in order; the last one repeats."""

    def __init__(self) -> None:
        self.replies: list[str] = [""]
        self.status = 200
        self.raw_body: bytes | None = None  # if set, sent verbatim instead of a chat completion
        self.delay = 0.0  # seconds to wait before answering a chat request
        self.reject_response_format = False  # answer 400 to any request that carries response_format
        self.requests: list[dict] = []
        self._lock = threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - http.server naming
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
                with fake._lock:
                    fake.requests.append({"path": self.path, "body": body})
                    status = fake.status
                    content = fake._next_reply()
                    raw_body = fake.raw_body
                    delay = fake.delay
                if delay:
                    time.sleep(delay)
                if fake.reject_response_format and "response_format" in body:
                    status = 400
                if status != 200:
                    data = b'{"error": "model not loaded"}'
                elif raw_body is not None:
                    data = raw_body
                else:
                    data = json.dumps(
                        {"choices": [{"message": {"role": "assistant", "content": content}}]}
                    ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format, *args):  # noqa: A002 - keep pytest output quiet
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}/v1"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def _next_reply(self) -> str:
        if len(self.replies) > 1:
            return self.replies.pop(0)
        return self.replies[0]

    def set_replies(self, *contents: str) -> None:
        with self._lock:
            self.replies = list(contents)

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(5)


def unreachable_url() -> str:
    """A base URL whose port nothing listens on (bound, read, then released)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}/v1"


def valid_challenge() -> dict:
    return {
        "title": "Model abstract",
        "situation": "You are writing for a thesis committee.",
        "task": "Write an abstract for the study.",
        "background": ["Pilot had 120 participants.", "Effect was small.", "One city only."],
        "requirements": ["Mention a limitation.", "Use one hedge.", "Use two linking words.", "State the aim."],
        "key_vocabulary": [{"term": "robustness", "meaning": "stability of a result"}],
        "plan_hints": ["Context", "Gap", "Evidence", "Limitation"],
    }


def grading_reply(scores: dict) -> str:
    return json.dumps(
        {
            "scores": scores,
            "strengths": ["Clear aim.", "Good hedging.", "Extra item"],
            "corrections": [{"original": "a", "revised": "b", "explanation": "why"}],
            "improved_version": "Polished text.",
            "next_focus": "Linking words.",
            "mini_exercise": "Rewrite one sentence.",
        }
    )


def words(n: int) -> str:
    return " ".join(["word"] * n)


@pytest.fixture(autouse=True)
def _reset_llm_caches():
    """Probe results and schema support are cached per URL; start every test with them cleared."""
    llm._probes.clear()
    llm._schema_supported.clear()
    yield
    llm._probes.clear()
    llm._schema_supported.clear()


@pytest.fixture
def fake_llm():
    fake = FakeLLM()
    yield fake
    fake.close()


@pytest.fixture
def make_settings(tmp_path):
    def _make(base_url: str | None = None, port: int = 0) -> Settings:
        return Settings(
            llm_base_url=base_url or unreachable_url(),
            llm_model="test-model",
            llm_timeout=5.0,
            db_path=tmp_path / "coach.sqlite3",
            host="127.0.0.1",
            port=port,
        )

    return _make


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(tmp_path / "store.sqlite3")
