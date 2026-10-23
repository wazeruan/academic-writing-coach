"""Minimal client for a local OpenAI-compatible chat server (LM Studio, Ollama, llama.cpp)."""

import http.client
import json
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from .config import Settings

PROBE_TIMEOUT = 3  # Seconds for quick checks (health, model list), so a hung server cannot stall a page.
PROBE_CACHE_SECONDS = 30
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class LLMError(RuntimeError):
    """The local model is unreachable, or its answer could not be used."""


class LLMUnavailable(LLMError):
    """The server could not be reached. Retrying immediately will not help."""


class LLMReplyError(LLMError):
    """The server answered, but the reply could not be used. A retry may succeed."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status  # HTTP status when the server answered with an error code.


# Small per-process caches. Probes are cheap but run on every page load, so cache them briefly.
_lock = threading.Lock()
_probes: dict[str, dict[str, Any]] = {}  # base URL -> {"at", "online", "model"}
_schema_supported: dict[str, bool] = {}  # base URL -> does the server accept response_format?


def _headers(settings: Settings, *, json_body: bool) -> dict[str, str]:
    headers = {"Content-Type": "application/json"} if json_body else {}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    return headers


def _get_json(url: str, settings: Settings) -> Any:
    request = urllib.request.Request(url, headers=_headers(settings, json_body=False))
    with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT) as response:
        return json.load(response)


def _pick_model(loaded: Any, default: Any) -> str | None:
    """Prefer a model that is already loaded (the default, if it is one), so requests never wait for a model swap."""
    names = [name for name in loaded if isinstance(name, str) and name] if isinstance(loaded, list) else []
    if default in names:
        return default
    if names:
        return names[0]
    return default if isinstance(default, str) and default else None


def _probe_server(settings: Settings, *, force: bool = False) -> dict[str, Any]:
    """Check the server once per PROBE_CACHE_SECONDS: is it up, and which model should requests use?

    oMLX reports the models it has loaded at /api/status, so the app follows whatever model you
    load there. Servers without that route (LM Studio, llama.cpp) fall back to /health's default model.
    """
    base = settings.llm_base_url.rstrip("/")
    with _lock:
        cached = _probes.get(base)
        if cached and not force and time.monotonic() - cached["at"] < PROBE_CACHE_SECONDS:
            return dict(cached)
    root = base.removesuffix("/v1")
    online, model = False, None
    try:
        status = _get_json(root + "/api/status", settings)
        online = True
        if isinstance(status, dict):
            model = _pick_model(status.get("loaded_models"), status.get("default_model"))
    except urllib.error.HTTPError:
        online = True  # The server answered; it just has no oMLX status route (or needs another key).
    except (urllib.error.URLError, OSError, ValueError):
        online = False
    if online and model is None:
        try:
            health = _get_json(root + "/health", settings)
            if isinstance(health, dict):
                model = _pick_model(None, health.get("default_model"))
        except (urllib.error.URLError, OSError, ValueError):
            pass
    result = {"at": time.monotonic(), "online": online, "model": model}
    with _lock:
        _probes[base] = result
    return dict(result)


def reachable(settings: Settings) -> bool:
    return _probe_server(settings)["online"]


def model_name(settings: Settings) -> str:
    """The configured model, or the one the server has loaded, so switching models needs no restart."""
    if settings.llm_model:
        return settings.llm_model
    return _probe_server(settings)["model"] or "local-model"


def chat(
    messages: list[dict[str, str]],
    settings: Settings,
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    schema: dict[str, Any] | None = None,
) -> str:
    base = settings.llm_base_url.rstrip("/")
    body: dict[str, Any] = {
        "model": model_name(settings),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    use_schema = schema is not None and _schema_supported.get(base, True)
    if use_schema:
        # Structured output makes small local models return valid JSON far more reliably.
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "reply", "strict": True, "schema": schema},
        }
    try:
        data = _post(base + "/chat/completions", body, settings)
    except LLMReplyError as exc:
        if use_schema and exc.status == 400:
            # The server may not accept response_format. Ask again without it, and remember
            # only if that works, so an unrelated 400 does not switch structured output off.
            body.pop("response_format")
            data = _post(base + "/chat/completions", body, settings)
            _schema_supported[base] = False
        else:
            raise

    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMReplyError(f"Unexpected response from local LLM: {str(data)[:300]}") from exc


def _post(url: str, body: dict[str, Any], settings: Settings) -> Any:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=_headers(settings, json_body=True), method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.llm_timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise LLMReplyError(f"Local LLM answered with HTTP {exc.code}: {exc.reason}", status=exc.code) from exc
    except http.client.HTTPException as exc:
        # The connection dropped mid-reply, usually because the model server stopped or ran out of memory.
        raise LLMUnavailable(
            "The local model stopped while answering. Check that LM Studio is still running, "
            "then try again. Your text is saved."
        ) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise LLMUnavailable(
            f"Local LLM is not reachable at {settings.llm_base_url} ({exc}). "
            "Start the LM Studio server and load a model."
        ) from exc


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model reply, tolerating reasoning blocks, fences and chatter."""
    cleaned = THINK_BLOCK.sub("", text).strip()
    decoder = json.JSONDecoder()
    # Try each "{" in turn, so stray braces in the chatter before the JSON are skipped.
    position = cleaned.find("{")
    while position != -1:
        try:
            parsed, _ = decoder.raw_decode(cleaned, position)
        except json.JSONDecodeError:
            position = cleaned.find("{", position + 1)
            continue
        if isinstance(parsed, dict):
            return parsed
        position = cleaned.find("{", position + 1)
    raise LLMReplyError(f"Model did not return a JSON object: {cleaned[:200]}")


def chat_json(
    messages: list[dict[str, str]],
    settings: Settings,
    *,
    retries: int = 1,
    **kwargs: Any,
) -> dict[str, Any]:
    """Ask for JSON; on an unusable reply, retry once at a lower temperature. Never retry an unreachable server."""
    attempt = 0
    while True:
        try:
            return extract_json(chat(messages, settings, **kwargs))
        except LLMReplyError:
            if attempt >= retries:
                raise
            attempt += 1
            kwargs["temperature"] = min(kwargs.get("temperature", 0.7), 0.2)


def status(settings: Settings) -> dict[str, Any]:
    """Report whether the server answers and which model the app will use."""
    probe = _probe_server(settings, force=True)
    return {"online": probe["online"], "model": model_name(settings)}
