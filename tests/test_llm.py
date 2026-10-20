import pytest

from academic_writing_coach import llm
from academic_writing_coach.llm import LLMError
from conftest import unreachable_url


# extract_json -----------------------------------------------------------------

def test_extract_json_plain_object():
    assert llm.extract_json('{"a": 1, "b": [2, 3]}') == {"a": 1, "b": [2, 3]}


def test_extract_json_strips_code_fences_and_chatter():
    text = 'Sure, here is the challenge:\n```json\n{"title": "T", "n": 2}\n```\nHope this helps!'
    assert llm.extract_json(text) == {"title": "T", "n": 2}


def test_extract_json_malformed_raises_llm_error():
    with pytest.raises(LLMError, match="JSON"):
        llm.extract_json('{"a": }')


def test_extract_json_skips_braces_in_chatter_before_the_object():
    assert llm.extract_json('Here is {the} result: {"a": 1}') == {"a": 1}


def test_extract_json_without_braces_raises_llm_error():
    with pytest.raises(LLMError, match="did not return a JSON object"):
        llm.extract_json("I cannot help with that.")


def test_extract_json_rejects_closing_brace_before_opening():
    with pytest.raises(LLMError):
        llm.extract_json("} oops {")


# chat / chat_json against the fake server ---------------------------------------

def test_chat_returns_content_and_sends_openai_request(fake_llm, make_settings):
    fake_llm.set_replies("hello there")
    settings = make_settings(fake_llm.url)

    assert llm.chat([{"role": "user", "content": "hi"}], settings, temperature=0.2) == "hello there"

    (request,) = fake_llm.requests
    assert request["path"] == "/v1/chat/completions"
    assert request["body"]["model"] == "test-model"
    assert request["body"]["messages"] == [{"role": "user", "content": "hi"}]
    assert request["body"]["temperature"] == 0.2
    assert request["body"]["stream"] is False


def test_chat_null_content_becomes_empty_string(fake_llm, make_settings):
    fake_llm.set_replies(None)
    assert llm.chat([{"role": "user", "content": "hi"}], make_settings(fake_llm.url)) == ""


def test_chat_json_parses_model_reply(fake_llm, make_settings):
    fake_llm.set_replies('Here you go:\n```json\n{"ok": true}\n```')
    assert llm.chat_json([{"role": "user", "content": "x"}], make_settings(fake_llm.url)) == {"ok": True}


def test_chat_http_error_raises_llm_error(fake_llm, make_settings):
    fake_llm.status = 500
    with pytest.raises(LLMError, match="HTTP 500"):
        llm.chat([{"role": "user", "content": "x"}], make_settings(fake_llm.url))


def test_chat_missing_choices_raises_llm_error(fake_llm, make_settings):
    fake_llm.raw_body = b'{"id": "x", "object": "chat.completion"}'
    with pytest.raises(LLMError, match="Unexpected response"):
        llm.chat([{"role": "user", "content": "x"}], make_settings(fake_llm.url))


def test_chat_non_json_body_raises_llm_error(fake_llm, make_settings):
    fake_llm.raw_body = b"<html>proxy error</html>"
    with pytest.raises(LLMError, match="not reachable"):
        llm.chat([{"role": "user", "content": "x"}], make_settings(fake_llm.url))


def test_chat_unreachable_url_raises_llm_error(make_settings):
    settings = make_settings(unreachable_url())
    with pytest.raises(LLMError, match="not reachable"):
        llm.chat([{"role": "user", "content": "x"}], settings)


def test_chat_json_unreachable_url_raises_llm_error(make_settings):
    settings = make_settings(unreachable_url())
    with pytest.raises(LLMError):
        llm.chat_json([{"role": "user", "content": "x"}], settings)


def test_status_reports_offline_for_unreachable_url(make_settings):
    result = llm.status(make_settings(unreachable_url()))
    assert result["online"] is False
    assert result["model"] == "test-model"
