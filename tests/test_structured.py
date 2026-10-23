"""Structured output, reasoning-block handling, retries, offline fallback, and concurrency."""

import json
import threading

import pytest

from academic_writing_coach import llm, service
from academic_writing_coach.curriculum import GRADING_RUBRIC, pick_scenario
from academic_writing_coach.llm import LLMReplyError, LLMUnavailable
from academic_writing_coach.lessons import UNITS

from conftest import DAY, unreachable_url, valid_challenge, words

MESSAGES = [{"role": "user", "content": "hi"}]
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


# Structured output ---------------------------------------------------------------

def test_response_format_is_sent_when_schema_given(fake_llm, make_settings):
    fake_llm.set_replies('{"ok": true}')

    assert llm.chat_json(MESSAGES, make_settings(fake_llm.url), schema=SCHEMA) == {"ok": True}

    (request,) = fake_llm.requests
    response_format = request["body"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["schema"] == SCHEMA
    assert response_format["json_schema"]["strict"] is True


def test_no_response_format_without_schema(fake_llm, make_settings):
    fake_llm.set_replies("hello")
    llm.chat(MESSAGES, make_settings(fake_llm.url))
    assert "response_format" not in fake_llm.requests[0]["body"]


def test_http_400_retries_without_response_format_and_later_calls_skip_it(fake_llm, make_settings):
    fake_llm.reject_response_format = True
    fake_llm.set_replies('{"ok": true}')
    settings = make_settings(fake_llm.url)

    assert llm.chat_json(MESSAGES, settings, schema=SCHEMA) == {"ok": True}
    assert len(fake_llm.requests) == 2
    assert "response_format" in fake_llm.requests[0]["body"]
    assert "response_format" not in fake_llm.requests[1]["body"]
    assert llm._schema_supported[settings.llm_base_url.rstrip("/")] is False

    assert llm.chat_json(MESSAGES, settings, schema=SCHEMA) == {"ok": True}
    assert len(fake_llm.requests) == 3
    assert "response_format" not in fake_llm.requests[2]["body"]


def test_unrelated_400_does_not_switch_structured_output_off(fake_llm, make_settings):
    fake_llm.status = 400  # every request fails, so the retry fails too
    settings = make_settings(fake_llm.url)

    with pytest.raises(LLMReplyError, match="HTTP 400"):
        llm.chat(MESSAGES, settings, schema=SCHEMA)

    assert settings.llm_base_url.rstrip("/") not in llm._schema_supported


# Reasoning blocks ----------------------------------------------------------------

def test_think_block_before_json_is_ignored():
    text = '<think>Let me consider {the} options first.</think>\n{"ok": true}'
    assert llm.extract_json(text) == {"ok": True}


def test_think_block_is_ignored_through_chat_json(fake_llm, make_settings):
    fake_llm.set_replies('<think>draft: {"ok": false}</think>{"ok": true}')
    assert llm.chat_json(MESSAGES, make_settings(fake_llm.url)) == {"ok": True}


# Retries ------------------------------------------------------------------------

def test_chat_json_retries_once_on_bad_reply_at_lower_temperature(fake_llm, make_settings):
    fake_llm.set_replies("Sorry, no JSON this time.", '{"ok": true}')

    result = llm.chat_json(MESSAGES, make_settings(fake_llm.url), temperature=0.9)

    assert result == {"ok": True}
    assert len(fake_llm.requests) == 2
    assert fake_llm.requests[0]["body"]["temperature"] == 0.9
    assert fake_llm.requests[1]["body"]["temperature"] <= 0.2


def test_chat_json_gives_up_after_one_retry(fake_llm, make_settings):
    fake_llm.set_replies("never json")

    with pytest.raises(LLMReplyError):
        llm.chat_json(MESSAGES, make_settings(fake_llm.url))
    assert len(fake_llm.requests) == 2


def test_chat_json_does_not_retry_unreachable_server(monkeypatch, make_settings):
    calls = []

    def fake_chat(*args, **kwargs):
        calls.append(kwargs)
        raise LLMUnavailable("down")

    monkeypatch.setattr(llm, "chat", fake_chat)
    with pytest.raises(LLMUnavailable):
        llm.chat_json(MESSAGES, make_settings(unreachable_url()))
    assert len(calls) == 1


def test_chat_json_real_unreachable_server_raises_unavailable(make_settings):
    with pytest.raises(LLMUnavailable):
        llm.chat_json(MESSAGES, make_settings(unreachable_url()))


# Offline fallback without calling the model -------------------------------------

def test_challenge_for_uses_template_without_calling_chat_when_offline(monkeypatch, make_settings, store):
    def refuse(*args, **kwargs):
        raise AssertionError("chat must not be called when the server is down")

    monkeypatch.setattr(llm, "reachable", lambda settings: False)
    monkeypatch.setattr(llm, "chat", refuse)

    challenge, source = service.challenge_for(make_settings(), store, DAY)

    assert source == "template"
    assert challenge["title"].startswith(pick_scenario(DAY).title)
    assert store.get_challenge(DAY) is None


def test_grade_raises_unavailable_when_offline(monkeypatch, make_settings, store):
    calls = []
    monkeypatch.setattr(llm, "chat", lambda *a, **k: calls.append(1))

    with pytest.raises(LLMUnavailable):
        service._grade(make_settings(unreachable_url()), store, valid_challenge(), words(40), "")
    assert calls == []


# requirements_met --------------------------------------------------------------

def test_requirements_met_is_normalised_and_capped(fake_llm, make_settings, store):
    challenge = valid_challenge()  # four requirements
    store.save_challenge(DAY, challenge)
    reply = {
        "scores": {key: 4 for key in GRADING_RUBRIC},
        "requirements_met": [
            {"requirement": "R1", "met": True, "note": "yes"},
            {"requirement": "R2", "met": "true", "note": "string is not True"},
            {"requirement": "R3", "met": 1, "note": "number is not True"},
            "not a dict",
            {"requirement": "R4", "met": False},
            {"requirement": "R5", "met": True},
            {"requirement": "R6", "met": True},
        ],
    }
    fake_llm.set_replies(json.dumps(reply))

    result = service.submit(make_settings(fake_llm.url), store, DAY, "", words(40))
    met = result["feedback"]["requirements_met"]

    assert len(met) == len(challenge["requirements"]) == 4
    assert [item["met"] for item in met] == [True, False, False, False]
    assert met[0] == {"requirement": "R1", "met": True, "note": "yes"}
    assert met[2]["note"] == "number is not True"
    assert met[3] == {"requirement": "R4", "met": False, "note": ""}


def test_requirements_met_missing_key_defaults_to_empty_list(fake_llm, make_settings, store):
    store.save_challenge(DAY, valid_challenge())
    fake_llm.set_replies(json.dumps({"scores": {key: 3 for key in GRADING_RUBRIC}}))

    result = service.submit(make_settings(fake_llm.url), store, DAY, "", words(40))

    assert result["feedback"]["requirements_met"] == []


# Concurrency ---------------------------------------------------------------------

def test_two_threads_generate_the_challenge_only_once(fake_llm, make_settings, store):
    fake_llm.set_replies(json.dumps(valid_challenge()))
    fake_llm.delay = 0.3  # keep the first call in flight while the second arrives
    settings = make_settings(fake_llm.url)
    barrier = threading.Barrier(2)
    results, errors = [], []

    def call():
        try:
            barrier.wait()
            results.append(service.challenge_for(settings, store, DAY))
        except Exception as exc:  # surfaced by the assertions below
            errors.append(exc)

    threads = [threading.Thread(target=call) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)

    assert errors == []
    assert len(fake_llm.requests) == 1
    assert [source for _, source in results] == ["model", "model"]
    assert all(challenge["title"] == "Model abstract" for challenge, _ in results)


def test_message_mentioning_400_without_status_400_does_not_retry(monkeypatch, make_settings):
    calls = []

    def fake_post(url, body, settings):
        calls.append(body)
        raise LLMReplyError("Local LLM answered with HTTP 400: mentioned in text only", status=500)

    monkeypatch.setattr(llm, "_post", fake_post)
    settings = make_settings()

    with pytest.raises(LLMReplyError, match="HTTP 400"):
        llm.chat(MESSAGES, settings, schema=SCHEMA)

    assert len(calls) == 1, "no retry without response_format when the status is not 400"
    assert "response_format" in calls[0]
    assert settings.llm_base_url.rstrip("/") not in llm._schema_supported


# Model server dies mid-reply ----------------------------------------------------

def test_truncated_reply_raises_unavailable_and_is_not_retried(truncating_llm, make_settings):
    settings = make_settings(truncating_llm.url)

    with pytest.raises(LLMUnavailable, match="stopped"):
        llm.chat(MESSAGES, settings)

    with pytest.raises(LLMUnavailable):
        llm.chat_json(MESSAGES, settings)
    assert truncating_llm.chat_requests == 2, "chat_json must not retry a server that stopped mid-reply"
