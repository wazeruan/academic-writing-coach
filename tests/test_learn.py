import json

import pytest

from academic_writing_coach import service
from academic_writing_coach.curriculum import GRADING_RUBRIC
from academic_writing_coach.lessons import PASS_SCORE, UNITS

from conftest import DAY, grading_reply, unreachable_url, valid_challenge, words


def grade(score: int) -> str:
    return grading_reply({key: score for key in GRADING_RUBRIC})


def statuses(store) -> list[str]:
    return [unit["status"] for unit in service.unit_statuses(store)]


def test_units_unlock_in_order(store):
    assert statuses(store) == ["current"] + ["locked"] * (len(UNITS) - 1)

    store.record_unit_score(UNITS[0].id, 80.0, True)
    assert statuses(store) == ["done", "current"] + ["locked"] * (len(UNITS) - 2)
    assert service.current_unit(store).id == UNITS[1].id

    store.record_unit_score(UNITS[1].id, 75.0, True)
    assert statuses(store)[:3] == ["done", "done", "current"]
    assert service.learn_overview(store)["completed"] == 2


def test_practice_submit_to_locked_unit_raises_value_error(fake_llm, make_settings, store):
    with pytest.raises(ValueError, match="Finish the earlier units first"):
        service.practice_submit(make_settings(fake_llm.url), store, UNITS[1].id, "task", "", words(40))
    assert fake_llm.requests == []
    assert store.unit_progress() == {}


def test_practice_start_on_locked_unit_raises_value_error(make_settings, store):
    with pytest.raises(ValueError, match="Finish the earlier units first"):
        service.practice_start(make_settings(unreachable_url()), store, UNITS[-1].id)


def test_passing_practice_completes_unit_and_unlocks_next(fake_llm, make_settings, store):
    fake_llm.set_replies(grade(4))  # overall 80, above PASS_SCORE
    assert PASS_SCORE == 70

    result = service.practice_submit(
        make_settings(fake_llm.url), store, UNITS[0].id, "Rewrite the paragraph.", "", words(40)
    )

    assert result["passed"] is True
    assert result["overall"] == 80.0
    assert result["unit"]["status"] == "done"
    overview = service.learn_overview(store)
    assert overview["units"][0]["status"] == "done"
    assert overview["units"][1]["status"] == "current"
    assert overview["completed"] == 1
    assert store.total_xp() == result["xp"]


def test_failing_practice_keeps_unit_current_and_best_score(fake_llm, make_settings, store):
    fake_llm.set_replies(grade(2), grade(3), grade(2))  # overall 40, 60, 40
    settings = make_settings(fake_llm.url)
    task = "Rewrite the paragraph."

    first = service.practice_submit(settings, store, UNITS[0].id, task, "", words(40))
    assert first["passed"] is False
    assert first["unit"]["status"] == "current"
    assert first["unit"]["best_overall"] == 40.0

    second = service.practice_submit(settings, store, UNITS[0].id, task, "", words(40))
    assert second["passed"] is False
    assert second["unit"]["best_overall"] == 60.0

    third = service.practice_submit(settings, store, UNITS[0].id, task, "", words(40))
    assert third["unit"]["status"] == "current"
    assert third["unit"]["best_overall"] == 60.0, "best score must not drop after a weaker attempt"
    assert service.learn_overview(store)["completed"] == 0
    assert len(store.submissions_for(DAY)) == 0  # practice never creates a daily submission


def test_daily_submit_passing_completes_challenge_unit(fake_llm, make_settings, store):
    store.save_challenge(DAY, {**valid_challenge(), "unit_id": UNITS[0].id})
    fake_llm.set_replies(grade(4))

    result = service.submit(make_settings(fake_llm.url), store, DAY, "", words(40))

    assert result["unit_passed"] is True
    assert service.unit_statuses(store)[0]["status"] == "done"
    assert service.current_unit(store).id == UNITS[1].id


def test_daily_submit_failing_leaves_unit_current(fake_llm, make_settings, store):
    store.save_challenge(DAY, {**valid_challenge(), "unit_id": UNITS[0].id})
    fake_llm.set_replies(grade(2))

    result = service.submit(make_settings(fake_llm.url), store, DAY, "", words(40))

    assert result["unit_passed"] is False
    assert service.unit_statuses(store)[0]["status"] == "current"


def test_challenge_for_carries_focus_unit_into_prompt(fake_llm, make_settings, store):
    fake_llm.set_replies(json.dumps(valid_challenge()))

    challenge, source = service.challenge_for(make_settings(fake_llm.url), store, DAY)

    assert source == "model"
    assert challenge["unit_id"] == UNITS[0].id
    assert challenge["focus_skill"] == UNITS[0].skill
    user_message = fake_llm.requests[0]["body"]["messages"][1]["content"]
    assert UNITS[0].skill in user_message


def test_practice_start_falls_back_to_unit_practice_task(make_settings, store):
    result = service.practice_start(make_settings(unreachable_url()), store, UNITS[0].id)

    assert result["source"] == "template"
    assert result["unit_id"] == UNITS[0].id
    assert result["task"] == UNITS[0].practice_task


def test_practice_start_uses_model_task_when_available(fake_llm, make_settings, store):
    fake_llm.set_replies('{"task": "  Revise the short paragraph about bus routes.  "}')

    result = service.practice_start(make_settings(fake_llm.url), store, UNITS[0].id)

    assert result == {
        "unit_id": UNITS[0].id,
        "task": "Revise the short paragraph about bus routes.",
        "source": "model",
    }


def test_practice_start_blank_model_task_falls_back(fake_llm, make_settings, store):
    fake_llm.set_replies('{"task": "   "}')

    result = service.practice_start(make_settings(fake_llm.url), store, UNITS[0].id)

    assert result["source"] == "template"
    assert result["task"] == UNITS[0].practice_task


def test_every_unit_is_complete_and_ids_are_unique():
    from academic_writing_coach.lessons import UNIT_IDS

    assert len(set(UNIT_IDS)) == len(UNITS)
    text_fields = ("title", "skill", "explanation", "weak", "strong", "why_it_works", "practice_task")
    for unit in UNITS:
        for field in text_fields:
            value = getattr(unit, field)
            assert isinstance(value, str) and value.strip(), f"{unit.id}.{field} is empty"
        assert len(unit.checklist) == 3, f"{unit.id} must have exactly 3 checklist items"
        assert all(isinstance(item, str) and item.strip() for item in unit.checklist), unit.id
