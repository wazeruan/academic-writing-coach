"""Minimal client for a local OpenAI-compatible chat server (LM Studio, Ollama, llama.cpp)."""

import json
import urllib.error
import urllib.request
from dataclasses import replace
from typing import Any

from .config import Settings


class LLMError(RuntimeError):
    """The local model is unreachable, or its answer could not be used."""


def _headers(settings: Settings, *, json_body: bool) -> dict[str, str]:
    headers = {"Content-Type": "application/json"} if json_body else {}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    return headers


def chat(
    messages: list[dict[str, str]],
    settings: Settings,
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    body = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        settings.llm_base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers=_headers(settings, json_body=True),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.llm_timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise LLMError(f"Local LLM answered with HTTP {exc.code}: {exc.reason}") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise LLMError(
            f"Local LLM is not reachable at {settings.llm_base_url} ({exc}). "
            "Start the LM Studio server and load a model."
        ) from exc

    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected response from local LLM: {str(data)[:300]}") from exc


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model reply, tolerating code fences and chatter."""
    cleaned = text.strip()
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
    raise LLMError(f"Model did not return a JSON object: {cleaned[:200]}")


def chat_json(messages: list[dict[str, str]], settings: Settings, **kwargs: Any) -> dict[str, Any]:
    return extract_json(chat(messages, settings, **kwargs))


def resolve_model(settings: Settings) -> Settings:
    """Fill in the model name when none is configured, using the server's default model.

    LM Studio requires a model name in every request. Its health probe reports the default model,
    so switching the served model in LM Studio only needs an app restart, not a code change.
    """
    if settings.llm_model:
        return settings
    request = urllib.request.Request(settings.llm_base_url.rstrip("/").removesuffix("/v1") + "/health")
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            default = json.load(response).get("default_model")
    except (urllib.error.URLError, OSError, ValueError, AttributeError):
        default = None
    return replace(settings, llm_model=default or "local-model")


def status(settings: Settings) -> dict[str, Any]:
    """Report whether the server answers and which models it lists."""
    request = urllib.request.Request(
        settings.llm_base_url.rstrip("/") + "/models", headers=_headers(settings, json_body=False)
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            data = json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"online": False, "model": settings.llm_model, "error": str(exc)}
    models = [item.get("id", "") for item in data.get("data", [])]
    return {"online": True, "model": settings.llm_model, "available": models}
