import dataclasses

import pytest

from academic_writing_coach import llm
from academic_writing_coach.llm import _pick_model

from conftest import unreachable_url


@pytest.mark.parametrize(
    ("loaded", "default", "expected"),
    [
        (["a", "b"], "b", "b"),           # default is loaded: use it
        (["a"], "z", "a"),                # default not loaded: first loaded model
        ([], "z", "z"),                   # nothing loaded: fall back to the default
        ([], None, None),                 # nothing known at all
        (None, "z", "z"),                 # loaded_models missing or not a list
        ("not-a-list", "d", "d"),
        ([1, None, "", "c"], "x", "c"),   # non-string and empty entries are ignored
        (["", 3], "", None),
        (["c"], 5, "c"),                  # non-string default is ignored
    ],
)
def test_pick_model(loaded, default, expected):
    assert _pick_model(loaded, default) == expected


def discovery_settings(make_settings, url, **changes):
    """Settings that let the probe choose the model (no COACH_LLM_MODEL override)."""
    return dataclasses.replace(make_settings(url), llm_model="", **changes)


def test_probe_picks_loaded_model_and_sends_bearer_key(fake_llm, make_settings):
    fake_llm.get_routes["/api/status"] = (200, {"loaded_models": ["other-model"], "default_model": "missing"})
    settings = discovery_settings(make_settings, fake_llm.url, llm_api_key="secret-key")

    probe = llm._probe_server(settings, force=True)

    assert probe == {**probe, "online": True, "model": "other-model"}
    status_calls = [r for r in fake_llm.get_requests if r["path"] == "/api/status"]
    assert status_calls and all(r["auth"] == "Bearer secret-key" for r in status_calls)
    assert llm.model_name(settings) == "other-model"


@pytest.mark.parametrize("status_code", [404, 401])
def test_status_error_falls_back_to_health_default_model(fake_llm, make_settings, status_code):
    fake_llm.get_routes["/api/status"] = (status_code, {"error": "no route"})
    fake_llm.get_routes["/health"] = (200, {"default_model": "health-model"})
    settings = discovery_settings(make_settings, fake_llm.url)

    probe = llm._probe_server(settings, force=True)

    assert probe["online"] is True
    assert probe["model"] == "health-model"


def test_unreachable_server_is_offline_with_no_model(make_settings):
    settings = discovery_settings(make_settings, unreachable_url())

    probe = llm._probe_server(settings, force=True)

    assert probe["online"] is False
    assert probe["model"] is None


def test_configured_model_overrides_discovery(fake_llm, make_settings):
    fake_llm.get_routes["/api/status"] = (200, {"loaded_models": ["loaded-model"], "default_model": "loaded-model"})
    settings = dataclasses.replace(make_settings(fake_llm.url), llm_model="explicit-model")

    assert llm.model_name(settings) == "explicit-model"
