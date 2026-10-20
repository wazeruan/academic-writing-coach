"""Application logic shared by the web server and tests."""

import math
from datetime import date
from typing import Any

from . import llm
from .config import Settings
from .curriculum import (
    GRADING_RUBRIC,
    LEVELS,
    SCENARIOS,
    generation_messages,
    grading_messages,
    pick_scenario,
    pick_topic,
    template_challenge,
)
from .store import Store, streak

MIN_WORDS_TO_SUBMIT = 30
REQUIRED_CHALLENGE_KEYS = ("title", "situation", "task", "background", "requirements", "plan_hints")


def word_count(text: str) -> int:
    return len(text.split())


TEXT_KEYS = ("title", "situation", "task")
LIST_KEYS = ("background", "requirements", "plan_hints")


def _valid_challenge(payload: dict[str, Any]) -> bool:
    """Check field types too: the page calls .map() on the list fields."""
    if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in TEXT_KEYS):
        return False
    return all(
        isinstance(payload.get(key), list)
        and payload[key]
        and all(isinstance(item, str) for item in payload[key])
        for key in LIST_KEYS
    )


def challenge_for(settings: Settings, store: Store, day: date) -> tuple[dict[str, Any], str]:
    """Return (challenge, source). Model-made challenges are cached per day; templates are not."""
    stored = store.get_challenge(day)
    if stored is not None:
        return stored, "model"

    level = store.get_setting("level", "intermediate")
    scenario = pick_scenario(day)
    topic = pick_topic(day)
    try:
        generated = llm.chat_json(generation_messages(scenario, level, topic), settings, temperature=0.9)
    except llm.LLMError:
        return template_challenge(scenario, level, topic), "template"

    if not _valid_challenge(generated):
        return template_challenge(scenario, level, topic), "template"

    generated["word_range"] = list(scenario.word_range)
    generated["level"] = level
    generated["scenario"] = scenario.key
    store.save_challenge(day, generated)
    return generated, "model"


def progress(store: Store, day: date) -> dict[str, Any]:
    days = store.submitted_days()
    return {
        "streak": streak(days, day),
        "days_completed": len(days),
        "total_xp": store.total_xp(),
        "average_overall": store.average_overall(),
        "done_today": day in days,
    }


def today(settings: Settings, store: Store, day: date) -> dict[str, Any]:
    challenge, source = challenge_for(settings, store, day)
    draft = store.get_draft(day)
    return {
        "date": day.isoformat(),
        "challenge": challenge,
        "source": source,
        "draft": draft,
        "word_count": word_count(draft["draft"]),
        "submissions": store.submissions_for(day),
        "latest": store.latest_submission(day),
        "progress": progress(store, day),
        "level": store.get_setting("level", "intermediate"),
        "levels": list(LEVELS),
        "rubric": GRADING_RUBRIC,
        "min_words": MIN_WORDS_TO_SUBMIT,
        "scenarios": [{"key": s.key, "title": s.title} for s in SCENARIOS],
    }


def save_draft(store: Store, day: date, plan: str, draft: str) -> dict[str, Any]:
    store.save_draft(day, plan, draft)
    return {"saved": True, "word_count": word_count(draft)}


def _clamp_score(value: Any) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 1
    if not math.isfinite(number):
        return 1
    return max(1, min(5, round(number)))


def _normalise_feedback(raw: dict[str, Any]) -> dict[str, Any]:
    scores_in = raw.get("scores")
    if not isinstance(scores_in, dict) or not any(key in scores_in for key in GRADING_RUBRIC):
        raise llm.LLMError("Model reply had no rubric scores; try submitting again.")
    scores = {key: _clamp_score(scores_in.get(key)) for key in GRADING_RUBRIC}
    corrections = [
        {
            "original": str(item.get("original", "")),
            "revised": str(item.get("revised", "")),
            "explanation": str(item.get("explanation", "")),
        }
        for item in raw.get("corrections", [])
        if isinstance(item, dict)
    ][:5]
    return {
        "scores": scores,
        "strengths": [str(s) for s in raw.get("strengths", [])][:3],
        "corrections": corrections,
        "improved_version": str(raw.get("improved_version", "")),
        "next_focus": str(raw.get("next_focus", "")),
        "mini_exercise": str(raw.get("mini_exercise", "")),
    }


def submit(settings: Settings, store: Store, day: date, plan: str, draft: str) -> dict[str, Any]:
    words = word_count(draft)
    if words < MIN_WORDS_TO_SUBMIT:
        raise ValueError(f"Write at least {MIN_WORDS_TO_SUBMIT} words before submitting ({words} so far).")

    challenge, _ = challenge_for(settings, store, day)
    level = store.get_setting("level", "intermediate")
    raw = llm.chat_json(grading_messages(challenge, draft, plan, level), settings, temperature=0.3, max_tokens=3000)
    feedback = _normalise_feedback(raw)

    average = sum(feedback["scores"].values()) / len(feedback["scores"])
    overall = round(average * 20, 1)  # 1-5 per criterion becomes 0-100 overall
    xp = 10 + round(average * 4)
    store.save_draft(day, plan, draft)
    submission_id = store.add_submission(day, plan, draft, words, overall, xp, feedback)
    return {
        "submission_id": submission_id,
        "overall": overall,
        "xp": xp,
        "feedback": feedback,
        "progress": progress(store, day),
    }


def set_level(store: Store, day: date, level: str) -> dict[str, Any]:
    if level not in LEVELS:
        raise ValueError(f"Level must be one of {', '.join(LEVELS)}.")
    store.set_setting("level", level)
    if not store.submissions_for(day):
        # Today's model-made challenge was written for the old level; regenerate it.
        store.delete_challenge(day)
    return {"level": level}


def health(settings: Settings) -> dict[str, Any]:
    return llm.status(settings)
