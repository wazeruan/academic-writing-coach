import json

from academic_writing_coach import llm, service
from academic_writing_coach.curriculum import (
    challenge_notes,
    grading_messages,
    pick_scenario,
    template_challenge,
)
from academic_writing_coach.service import MIN_NOTES

from conftest import DAY, valid_challenge


def note(label, value):
    return {"label": label, "value": value}


def six_notes():
    return [note(f"L{i}", f"value {i}") for i in range(6)]


def test_model_challenge_with_fewer_than_six_notes_falls_back_to_template(fake_llm, make_settings, store):
    challenge = {**valid_challenge(), "notes": six_notes()[:5]}
    fake_llm.set_replies(json.dumps(challenge))

    _, source = service.challenge_for(make_settings(fake_llm.url), store, DAY)

    assert source == "template"
    assert store.get_challenge(DAY) is None


def test_model_challenge_with_a_note_missing_value_falls_back_to_template(fake_llm, make_settings, store):
    notes = six_notes()
    notes[3] = {"label": "Metric"}
    fake_llm.set_replies(json.dumps({**valid_challenge(), "notes": notes}))

    _, source = service.challenge_for(make_settings(fake_llm.url), store, DAY)

    assert source == "template"


def test_duplicate_notes_are_removed_from_saved_challenge(fake_llm, make_settings, store):
    notes = six_notes() + [note("L0", "VALUE 0")]  # same label and value, different case
    fake_llm.set_replies(json.dumps({**valid_challenge(), "notes": notes}))

    challenge, source = service.challenge_for(make_settings(fake_llm.url), store, DAY)

    assert source == "model"
    assert len(challenge["notes"]) == 6
    assert len({(n["label"].lower(), n["value"].lower()) for n in challenge["notes"]}) == 6


def test_duplicates_cannot_push_saved_notes_below_the_minimum(fake_llm, make_settings, store):
    # Six notes, one duplicated: only five distinct notes remain, so the challenge should not be saved.
    notes = six_notes()[:5] + [note("L0", "value 0")]
    fake_llm.set_replies(json.dumps({**valid_challenge(), "notes": notes}))

    challenge, source = service.challenge_for(make_settings(fake_llm.url), store, DAY)

    assert len(challenge["notes"]) >= MIN_NOTES
    assert source == "template"


def test_challenge_notes_formats_notes_as_label_value_lines():
    challenge = {"notes": [note("System", "a tutor"), note("Metric", "exam score")]}
    assert challenge_notes(challenge) == ["System: a tutor", "Metric: exam score"]


def test_challenge_notes_falls_back_to_old_background_sentences():
    challenge = {"background": ["Pilot had 120 participants.", "Effect was small."]}
    assert challenge_notes(challenge) == ["Pilot had 120 participants.", "Effect was small."]


def test_challenge_notes_with_neither_returns_empty_list():
    assert challenge_notes({}) == []
    assert challenge_notes({"notes": [], "background": []}) == []


def test_grading_prompt_contains_the_notes():
    challenge = {**valid_challenge(), "notes": [note("System", "tutoring model")] + six_notes()[1:]}
    messages = grading_messages(challenge, "draft text " * 10, "", "intermediate")

    user = messages[1]["content"]
    assert "System: tutoring model" in user
    assert "L1: value 1" in user


def test_template_challenge_passes_validation():
    scenario = pick_scenario(DAY)
    challenge = template_challenge(scenario, "intermediate", "sleep and memory")
    assert len(challenge["notes"]) >= MIN_NOTES
    assert service._valid_challenge(challenge)
