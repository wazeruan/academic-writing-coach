import json

import pytest

from academic_writing_coach import service
from academic_writing_coach.llm import LLMError
from academic_writing_coach.curriculum import pick_scenario
from academic_writing_coach.store import Store

from conftest import DAY, grading_reply, unreachable_url, valid_challenge, words


# challenge_for ---------------------------------------------------------------

def test_challenge_for_falls_back_to_template_when_llm_down(make_settings, store):
    settings = make_settings(unreachable_url())

    challenge, source = service.challenge_for(settings, store, DAY)

    assert source == "template"
    assert challenge["title"].startswith(pick_scenario(DAY).title)
    assert challenge["word_range"] == list(pick_scenario(DAY).word_range)
    # Template output is not cached, so a later online attempt can still replace it.
    assert store.get_challenge(DAY) is None


def test_challenge_for_caches_model_challenge(fake_llm, make_settings, store):
    fake_llm.set_replies(json.dumps(valid_challenge()))
    settings = make_settings(fake_llm.url)

    challenge, source = service.challenge_for(settings, store, DAY)
    again, source_again = service.challenge_for(settings, store, DAY)

    assert source == "model"
    assert challenge["title"] == "Model abstract"
    assert challenge["scenario"] == pick_scenario(DAY).key
    assert challenge["level"] == "intermediate"
    assert challenge["word_range"] == list(pick_scenario(DAY).word_range)
    assert source_again == "model"
    assert again["title"] == "Model abstract"
    assert len(fake_llm.requests) == 1, "second call should be served from the cache"


def test_challenge_for_invalid_json_from_model_falls_back_to_template(fake_llm, make_settings, store):
    fake_llm.set_replies("Sorry, I cannot produce a challenge today.")

    _, source = service.challenge_for(make_settings(fake_llm.url), store, DAY)

    assert source == "template"
    assert store.get_challenge(DAY) is None


def test_challenge_for_missing_required_keys_falls_back_to_template(fake_llm, make_settings, store):
    fake_llm.set_replies('{"title": "Only a title"}')

    _, source = service.challenge_for(make_settings(fake_llm.url), store, DAY)

    assert source == "template"
    assert store.get_challenge(DAY) is None


def test_challenge_for_rejects_model_challenge_with_wrong_field_types(fake_llm, make_settings, store):
    # app.js calls .map() on background, requirements and plan_hints, so a string here
    # would break the page. The service should not accept or cache it.
    broken = valid_challenge()
    broken["background"] = "one long string instead of a list"
    fake_llm.set_replies(json.dumps(broken))

    _, source = service.challenge_for(make_settings(fake_llm.url), store, DAY)

    assert source == "template"
    assert store.get_challenge(DAY) is None


# submit ------------------------------------------------------------------------

def test_submit_rejects_under_thirty_words_without_calling_model(fake_llm, make_settings, store):
    settings = make_settings(fake_llm.url)

    with pytest.raises(ValueError, match="at least 30 words"):
        service.submit(settings, store, DAY, "", words(29))

    assert fake_llm.requests == []
    assert store.submissions_for(DAY) == []


def test_submit_accepts_exactly_thirty_words(fake_llm, make_settings, store):
    store.save_challenge(DAY, valid_challenge())
    fake_llm.set_replies(grading_reply({"task_fulfilment": 3, "argument_clarity": 3,
                                        "organization": 3, "academic_register": 3,
                                        "grammar_accuracy": 3, "vocabulary_precision": 3}))

    result = service.submit(make_settings(fake_llm.url), store, DAY, "", words(30))

    assert result["overall"] == 60.0


def test_submit_clamps_scores_and_computes_overall_and_xp(fake_llm, make_settings, store):
    store.save_challenge(DAY, valid_challenge())
    fake_llm.set_replies(grading_reply({
        "task_fulfilment": 9,        # clamps to 5
        "argument_clarity": 0,       # clamps to 1
        "organization": 3.6,         # rounds to 4
        "academic_register": "4",    # string number -> 4
        "grammar_accuracy": "x",     # not a number -> 1
        "vocabulary_precision": 5,
    }))
    settings = make_settings(fake_llm.url)
    draft = words(40)

    result = service.submit(settings, store, DAY, "outline", draft)

    scores = result["feedback"]["scores"]
    assert scores == {
        "task_fulfilment": 5,
        "argument_clarity": 1,
        "organization": 4,
        "academic_register": 4,
        "grammar_accuracy": 1,
        "vocabulary_precision": 5,
    }
    average = 20 / 6
    assert result["overall"] == round(average * 20, 1) == 66.7
    assert result["xp"] == 10 + round(average * 4) == 23

    (row,) = store.submissions_for(DAY)
    assert row["overall"] == 66.7
    assert row["xp"] == 23
    assert row["word_count"] == 40
    assert store.get_draft(DAY) == {"plan": "outline", "draft": draft}
    assert result["progress"]["done_today"] is True


def test_submit_missing_scores_raise_llm_error(fake_llm, make_settings, store):
    store.save_challenge(DAY, valid_challenge())
    fake_llm.set_replies('{"scores": {}, "strengths": [], "corrections": []}')

    with pytest.raises(LLMError, match="no rubric scores"):
        service.submit(make_settings(fake_llm.url), store, DAY, "", words(35))
    assert store.submissions_for(DAY) == []


def test_submit_infinite_score_is_treated_as_invalid(fake_llm, make_settings, store):
    # json.loads accepts the non-standard token Infinity. _clamp_score handles NaN and
    # strings, but round(float("inf")) raises OverflowError, which is not caught.
    store.save_challenge(DAY, valid_challenge())
    fake_llm.set_replies('{"scores": {"task_fulfilment": Infinity}}')

    result = service.submit(make_settings(fake_llm.url), store, DAY, "", words(35))

    assert result["feedback"]["scores"]["task_fulfilment"] == 1


def test_submit_model_down_raises_llm_error(make_settings, store):
    from academic_writing_coach.llm import LLMError

    store.save_challenge(DAY, valid_challenge())
    with pytest.raises(LLMError):
        service.submit(make_settings(unreachable_url()), store, DAY, "", words(35))
    assert store.submissions_for(DAY) == []


# set_level ----------------------------------------------------------------------

def test_set_level_rejects_unknown_level(store):
    with pytest.raises(ValueError, match="Level must be one of"):
        service.set_level(store, DAY, "expert")
    assert store.get_setting("level", "intermediate") == "intermediate"


def test_set_level_clears_cached_model_challenge_without_submissions(store):
    store.save_challenge(DAY, valid_challenge())

    result = service.set_level(store, DAY, "advanced")

    assert result == {"level": "advanced"}
    assert store.get_setting("level", "intermediate") == "advanced"
    assert store.get_challenge(DAY) is None


def test_set_level_keeps_challenge_once_submitted(store):
    store.save_challenge(DAY, valid_challenge())
    store.add_submission(DAY, "", words(35), 35, 60.0, 20, {"scores": {}})

    service.set_level(store, DAY, "beginner")

    assert store.get_setting("level", "intermediate") == "beginner"
    assert store.get_challenge(DAY) is not None


# today / progress ---------------------------------------------------------------

def test_today_payload_with_llm_down(make_settings, store):
    payload = service.today(make_settings(unreachable_url()), store, DAY)

    assert payload["source"] == "template"
    assert payload["date"] == DAY.isoformat()
    assert payload["word_count"] == 0
    assert payload["progress"] == {
        "streak": 0,
        "days_completed": 0,
        "total_xp": 0,
        "average_overall": None,
        "done_today": False,
    }
