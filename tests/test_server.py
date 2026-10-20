import http.client
import json
import threading

import pytest

from academic_writing_coach.server import STATIC_DIR, make_server
from academic_writing_coach.store import Store

from conftest import unreachable_url, words


@pytest.fixture
def server(tmp_path, make_settings):
    settings = make_settings(unreachable_url(), port=0)
    httpd = make_server(settings, Store(tmp_path / "server.sqlite3"))
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(5)


def _request(httpd, method, path, body=None, raw=None):
    host, port = httpd.server_address[:2]
    conn = http.client.HTTPConnection(host, port, timeout=10)
    headers = {}
    payload = None
    if raw is not None:
        payload = raw
        headers["Content-Type"] = "application/json"
    elif body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    try:
        # http.client sends the path verbatim, so dot segments reach the server unnormalised.
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        return response.status, response.getheader("Content-Type"), response.read()
    finally:
        conn.close()


def _json(httpd, method, path, body=None, raw=None):
    status, _, data = _request(httpd, method, path, body=body, raw=raw)
    return status, json.loads(data)


def test_index_page_is_served(server):
    status, ctype, data = _request(server, "GET", "/")
    assert status == 200
    assert ctype.startswith("text/html")
    assert data == (STATIC_DIR / "index.html").read_bytes()


def test_static_app_js_is_served(server):
    status, ctype, data = _request(server, "GET", "/static/app.js")
    assert status == 200
    assert "javascript" in ctype
    assert data == (STATIC_DIR / "app.js").read_bytes()


def test_api_today_returns_template_when_llm_down(server):
    status, payload = _json(server, "GET", "/api/today")
    assert status == 200
    assert payload["source"] == "template"
    assert payload["challenge"]["title"]
    assert payload["min_words"] == 30
    assert payload["levels"] == ["beginner", "intermediate", "advanced"]


def test_api_health_reports_offline(server):
    status, payload = _json(server, "GET", "/api/health")
    assert status == 200
    assert payload["online"] is False


def test_post_draft_saves_text(server):
    status, payload = _json(server, "POST", "/api/draft", body={"plan": "p", "draft": "one two three"})
    assert status == 200
    assert payload == {"saved": True, "word_count": 3}

    _, today = _json(server, "GET", "/api/today")
    assert today["draft"] == {"plan": "p", "draft": "one two three"}


def test_post_submit_with_short_text_returns_400(server):
    status, payload = _json(server, "POST", "/api/submit", body={"plan": "", "draft": words(5)})
    assert status == 400
    assert "at least 30 words" in payload["error"]


def test_post_submit_with_llm_down_returns_502(server):
    status, payload = _json(server, "POST", "/api/submit", body={"plan": "", "draft": words(40)})
    assert status == 502
    assert "not reachable" in payload["error"]


def test_post_level_rejects_unknown_level(server):
    status, payload = _json(server, "POST", "/api/level", body={"level": "expert"})
    assert status == 400
    assert "Level must be one of" in payload["error"]


def test_path_traversal_under_static_returns_404(server):
    status, ctype, data = _request(server, "GET", "/static/../server.py")
    assert status == 404
    assert json.loads(data) == {"error": "Not found"}


def test_encoded_path_traversal_returns_404(server):
    status, _, _ = _request(server, "GET", "/static/%2e%2e/server.py")
    assert status == 404


def test_unknown_routes_return_404(server):
    assert _request(server, "GET", "/nope")[0] == 404
    assert _request(server, "POST", "/api/nope", body={})[0] == 404


def test_malformed_json_body_returns_400(server):
    status, payload = _json(server, "POST", "/api/draft", raw=b"{not json")
    assert status == 400
    assert payload["error"] == "Body must be JSON"


def test_non_object_json_body_returns_400(server):
    status, payload = _json(server, "POST", "/api/draft", raw=b"[1, 2]")
    assert status == 400
    assert payload["error"] == "Body must be a JSON object"


def test_non_string_field_returns_400(server):
    status, payload = _json(server, "POST", "/api/draft", body={"plan": 1, "draft": "x"})
    assert status == 400
    assert "'plan' must be a string" in payload["error"]
