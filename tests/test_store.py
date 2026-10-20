from datetime import timedelta

from academic_writing_coach.store import streak

from conftest import DAY


def test_streak_counts_consecutive_days_ending_today():
    days = {DAY, DAY - timedelta(days=1), DAY - timedelta(days=2)}
    assert streak(days, DAY) == 3


def test_streak_counts_from_yesterday_when_today_not_submitted():
    days = {DAY - timedelta(days=1), DAY - timedelta(days=2)}
    assert streak(days, DAY) == 2


def test_streak_stops_at_first_gap():
    days = {DAY, DAY - timedelta(days=2), DAY - timedelta(days=3)}
    assert streak(days, DAY) == 1


def test_streak_is_zero_when_last_submission_is_older_than_yesterday():
    days = {DAY - timedelta(days=2), DAY - timedelta(days=3)}
    assert streak(days, DAY) == 0


def test_streak_empty_is_zero():
    assert streak(set(), DAY) == 0


def test_store_draft_defaults_and_round_trip(store):
    assert store.get_draft(DAY) == {"plan": "", "draft": ""}
    store.save_draft(DAY, "outline", "some text")
    store.save_draft(DAY, "outline 2", "newer text")
    assert store.get_draft(DAY) == {"plan": "outline 2", "draft": "newer text"}


def test_store_submissions_aggregate_per_day(store):
    yesterday = DAY - timedelta(days=1)
    store.add_submission(yesterday, "", "a", 40, 60.0, 20, {"scores": {}})
    first = store.add_submission(DAY, "", "b", 45, 80.0, 30, {"scores": {}})
    store.add_submission(DAY, "", "c", 50, 40.0, 14, {"scores": {}})

    assert first > 0
    assert store.submitted_days() == {yesterday, DAY}
    assert store.total_xp() == 64
    assert store.latest_submission(DAY)["overall"] == 40.0
    assert [row["xp"] for row in store.submissions_for(DAY)] == [30, 14]
