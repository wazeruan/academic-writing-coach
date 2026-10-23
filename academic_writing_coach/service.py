"""Application logic shared by the web server and tests."""

import math
import threading
from datetime import date
from typing import Any

from . import llm
from .config import Settings
from .curriculum import (
    CHALLENGE_SCHEMA,
    GRADING_RUBRIC,
    GRADING_SCHEMA,
    LEVELS,
    PRACTICE_SCHEMA,
    SCENARIOS,
    generation_messages,
    grading_messages,
    pick_scenario,
    pick_topic,
    practice_messages,
    template_challenge,
)
from .lessons import PASS_SCORE, UNITS, Unit, unit_by_id
from .store import Store, streak

MIN_WORDS_TO_SUBMIT = 30
MAX_TASK_CHARS = 2000
TEXT_KEYS = ("title", "situation", "task")
LIST_KEYS = ("background", "requirements", "plan_hints")
_generation_lock = threading.Lock()


def word_count(text: str) -> int:
    return len(text.split())


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


# Learn units ---------------------------------------------------------------

def unit_statuses(store: Store) -> list[dict[str, Any]]:
    """Units in order, each marked done, current (the focus), or locked."""
    progress = store.unit_progress()
    current_found = False
    statuses = []
    for index, unit in enumerate(UNITS):
        record = progress.get(unit.id)
        if record and record["completed_at"]:
            status = "done"
        elif not current_found:
            status = "current"
            current_found = True
        else:
            status = "locked"
        statuses.append({
            "id": unit.id,
            "index": index,
            "title": unit.title,
            "skill": unit.skill,
            "status": status,
            "best_overall": record["best_overall"] if record else None,
        })
    return statuses


def current_unit(store: Store) -> Unit:
    """The focus unit: the first incomplete one, or the last unit once the course is finished."""
    for status in unit_statuses(store):
        if status["status"] == "current":
            return UNITS[status["index"]]
    return UNITS[-1]


def _ensure_unlocked(store: Store, unit_id: str) -> Unit:
    try:
        unit = unit_by_id(unit_id)
    except KeyError as exc:
        raise ValueError(f"Unknown unit: {unit_id}") from exc
    status = next(s["status"] for s in unit_statuses(store) if s["id"] == unit_id)
    if status == "locked":
        raise ValueError("Finish the earlier units first.")
    return unit


def unit_detail(store: Store, unit_id: str) -> dict[str, Any]:
    unit = _ensure_unlocked(store, unit_id)
    status = next(s for s in unit_statuses(store) if s["id"] == unit_id)
    return {
        "id": unit.id,
        "index": status["index"],
        "title": unit.title,
        "skill": unit.skill,
        "explanation": unit.explanation,
        "weak": unit.weak,
        "strong": unit.strong,
        "why_it_works": unit.why_it_works,
        "checklist": list(unit.checklist),
        "status": status["status"],
        "best_overall": status["best_overall"],
        "pass_score": PASS_SCORE,
    }


def learn_overview(store: Store) -> dict[str, Any]:
    statuses = unit_statuses(store)
    return {
        "units": statuses,
        "completed": sum(1 for s in statuses if s["status"] == "done"),
        "total": len(statuses),
        "pass_score": PASS_SCORE,
    }


# Daily challenge ----------------------------------------------------------

def challenge_for(settings: Settings, store: Store, day: date) -> tuple[dict[str, Any], str]:
    """Return (challenge, source). Model-made challenges are cached per day; templates are not."""
    stored = store.get_challenge(day)
    if stored is not None:
        return stored, "model"

    # One generation at a time: the startup warm-up and the first page load must not both call the model.
    with _generation_lock:
        stored = store.get_challenge(day)
        if stored is not None:
            return stored, "model"
        return _generate_challenge(settings, store, day)


def _generate_challenge(settings: Settings, store: Store, day: date) -> tuple[dict[str, Any], str]:
    level = store.get_setting("level", "intermediate")
    scenario = pick_scenario(day)
    topic = pick_topic(day)
    unit = current_unit(store)
    try:
        # A quick probe first, so a stopped or hung server falls back in seconds, not after the full timeout.
        if not llm.reachable(settings):
            raise llm.LLMUnavailable("Local LLM is offline")
        generated = llm.chat_json(
            generation_messages(scenario, level, topic, focus_skill=unit.skill),
            settings,
            temperature=0.9,
            schema=CHALLENGE_SCHEMA,
        )
        source = "model"
    except llm.LLMError:
        generated, source = template_challenge(scenario, level, topic), "template"

    if not _valid_challenge(generated):
        generated, source = template_challenge(scenario, level, topic), "template"

    generated["word_range"] = list(scenario.word_range)
    generated["level"] = level
    generated["scenario"] = scenario.key
    generated["unit_id"] = unit.id
    generated["focus_skill"] = unit.skill
    if source == "model":
        store.save_challenge(day, generated)
    return generated, source


def warm_today(settings: Settings, store: Store, day: date) -> None:
    """Generate today's challenge in the background at startup, so the first page load does not wait."""
    try:
        challenge_for(settings, store, day)
    except Exception:  # Best effort: the page load tries again and reports any error.
        pass


def progress(store: Store, day: date) -> dict[str, Any]:
    days = store.submitted_days()
    completed = sum(1 for s in unit_statuses(store) if s["status"] == "done")
    return {
        "streak": streak(days, day),
        "days_completed": len(days),
        "total_xp": store.total_xp(),
        "average_overall": store.average_overall(),
        "done_today": day in days,
        "units_completed": completed,
        "units_total": len(UNITS),
    }


def today(settings: Settings, store: Store, day: date) -> dict[str, Any]:
    challenge, source = challenge_for(settings, store, day)
    draft = store.get_draft(day)
    unit = current_unit(store)
    return {
        "date": day.isoformat(),
        "challenge": challenge,
        "source": source,
        "focus": {"id": unit.id, "title": unit.title, "skill": unit.skill},
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


# Grading -----------------------------------------------------------------

def _clamp_score(value: Any) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 1
    if not math.isfinite(number):
        return 1
    return max(1, min(5, round(number)))


def _normalise_feedback(raw: dict[str, Any], requirement_count: int) -> dict[str, Any]:
    scores_in = raw.get("scores")
    if not isinstance(scores_in, dict) or not any(key in scores_in for key in GRADING_RUBRIC):
        raise llm.LLMReplyError("Model reply had no rubric scores; try submitting again.")
    scores = {key: _clamp_score(scores_in.get(key)) for key in GRADING_RUBRIC}
    requirements_met = [
        {
            "requirement": str(item.get("requirement", "")),
            "met": item.get("met") is True,
            "note": str(item.get("note", "")),
        }
        for item in raw.get("requirements_met", [])
        if isinstance(item, dict)
    ][:requirement_count]
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
        "requirements_met": requirements_met,
        "strengths": [str(s) for s in raw.get("strengths", [])][:3],
        "corrections": corrections,
        "improved_version": str(raw.get("improved_version", "")),
        "next_focus": str(raw.get("next_focus", "")),
        "mini_exercise": str(raw.get("mini_exercise", "")),
    }


def _grade(settings: Settings, store: Store, challenge: dict[str, Any], draft: str, plan: str) -> dict[str, Any]:
    if not llm.reachable(settings):
        raise llm.LLMUnavailable("The local model is offline, so this cannot be graded yet. Your text is saved.")
    level = store.get_setting("level", "intermediate")
    messages = grading_messages(challenge, draft, plan, level)
    requirement_count = len(challenge.get("requirements", []))
    for attempt in range(2):  # One retry when the reply parses but has no usable scores.
        raw = llm.chat_json(messages, settings, temperature=0.2, max_tokens=3000, schema=GRADING_SCHEMA)
        try:
            feedback = _normalise_feedback(raw, requirement_count)
            break
        except llm.LLMReplyError:
            if attempt == 1:
                raise
    average = sum(feedback["scores"].values()) / len(feedback["scores"])
    return {
        "feedback": feedback,
        "overall": round(average * 20, 1),  # 1-5 per criterion becomes 0-100 overall
        "xp": 10 + round(average * 4),
    }


def submit(settings: Settings, store: Store, day: date, plan: str, draft: str) -> dict[str, Any]:
    """Daily submission. Passing it also completes the unit that the challenge focused on."""
    words = word_count(draft)
    if words < MIN_WORDS_TO_SUBMIT:
        raise ValueError(f"Write at least {MIN_WORDS_TO_SUBMIT} words before submitting ({words} so far).")

    challenge, _ = challenge_for(settings, store, day)
    graded = _grade(settings, store, challenge, draft, plan)
    store.save_draft(day, plan, draft)
    submission_id = store.add_submission(
        day, plan, draft, words, graded["overall"], graded["xp"], graded["feedback"]
    )
    unit_id = challenge.get("unit_id")
    passed = graded["overall"] >= PASS_SCORE
    if unit_id in {unit.id for unit in UNITS}:
        store.record_unit_score(unit_id, graded["overall"], passed)
    return {
        "submission_id": submission_id,
        "overall": graded["overall"],
        "xp": graded["xp"],
        "feedback": graded["feedback"],
        "unit_passed": passed,
        "progress": progress(store, day),
    }


# Learn practice ----------------------------------------------------------

def practice_start(settings: Settings, store: Store, unit_id: str) -> dict[str, Any]:
    unit = _ensure_unlocked(store, unit_id)
    level = store.get_setting("level", "intermediate")
    try:
        if not llm.reachable(settings):
            raise llm.LLMUnavailable("Local LLM is offline")
        generated = llm.chat_json(
            practice_messages(unit.title, unit.skill, level, unit.practice_task),
            settings,
            temperature=0.9,
            schema=PRACTICE_SCHEMA,
        )
        task = generated.get("task")
        source = "model"
        if not isinstance(task, str) or not task.strip():
            raise llm.LLMError("No task in model reply")
    except llm.LLMError:
        task, source = unit.practice_task, "template"
    return {"unit_id": unit.id, "task": task.strip()[:MAX_TASK_CHARS], "source": source}


def practice_submit(
    settings: Settings, store: Store, unit_id: str, task: str, plan: str, draft: str
) -> dict[str, Any]:
    unit = _ensure_unlocked(store, unit_id)
    words = word_count(draft)
    if words < MIN_WORDS_TO_SUBMIT:
        raise ValueError(f"Write at least {MIN_WORDS_TO_SUBMIT} words before submitting ({words} so far).")
    exercise = {
        "title": unit.title,
        "situation": "Practice exercise for one Learn unit.",
        "task": task[:MAX_TASK_CHARS] or unit.practice_task,
        "background": [],
        "requirements": list(unit.checklist),
    }
    graded = _grade(settings, store, exercise, draft, plan)
    passed = graded["overall"] >= PASS_SCORE
    attempt_id = store.add_practice(
        unit.id, exercise["task"], plan, draft, graded["overall"], graded["xp"], graded["feedback"]
    )
    store.record_unit_score(unit.id, graded["overall"], passed)
    return {
        "attempt_id": attempt_id,
        "overall": graded["overall"],
        "xp": graded["xp"],
        "passed": passed,
        "feedback": graded["feedback"],
        "unit": unit_detail(store, unit.id),
    }


# Settings and health ----------------------------------------------------

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
