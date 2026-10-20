"""SQLite persistence: challenges, drafts, graded submissions, and settings."""

import json
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS challenges (
    day TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    day TEXT PRIMARY KEY,
    plan TEXT NOT NULL DEFAULT '',
    draft TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    draft TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT '',
    word_count INTEGER NOT NULL,
    overall REAL NOT NULL,
    xp INTEGER NOT NULL,
    feedback TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS submissions_day ON submissions(day);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS practice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id TEXT NOT NULL,
    task TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT '',
    draft TEXT NOT NULL,
    overall REAL NOT NULL,
    xp INTEGER NOT NULL,
    feedback TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS unit_progress (
    unit_id TEXT PRIMARY KEY,
    best_overall REAL NOT NULL,
    completed_at TEXT
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def _execute(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cursor = self._conn.execute(sql, params)
            rows = cursor.fetchall()
            self._conn.commit()
            return rows

    # Challenges -----------------------------------------------------------
    def get_challenge(self, day: date) -> dict | None:
        rows = self._execute("SELECT payload FROM challenges WHERE day = ?", (day.isoformat(),))
        return json.loads(rows[0]["payload"]) if rows else None

    def save_challenge(self, day: date, payload: dict) -> None:
        self._execute(
            "INSERT OR REPLACE INTO challenges (day, payload, created_at) VALUES (?, ?, ?)",
            (day.isoformat(), json.dumps(payload), _now()),
        )

    def delete_challenge(self, day: date) -> None:
        self._execute("DELETE FROM challenges WHERE day = ?", (day.isoformat(),))

    # Drafts ---------------------------------------------------------------
    def get_draft(self, day: date) -> dict:
        rows = self._execute("SELECT plan, draft FROM drafts WHERE day = ?", (day.isoformat(),))
        if not rows:
            return {"plan": "", "draft": ""}
        return {"plan": rows[0]["plan"], "draft": rows[0]["draft"]}

    def save_draft(self, day: date, plan: str, draft: str) -> None:
        self._execute(
            "INSERT OR REPLACE INTO drafts (day, plan, draft, updated_at) VALUES (?, ?, ?, ?)",
            (day.isoformat(), plan, draft, _now()),
        )

    # Submissions ----------------------------------------------------------
    def add_submission(
        self, day: date, plan: str, draft: str, word_count: int, overall: float, xp: int, feedback: dict
    ) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO submissions (day, draft, plan, word_count, overall, xp, feedback, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (day.isoformat(), draft, plan, word_count, overall, xp, json.dumps(feedback), _now()),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

    def submissions_for(self, day: date) -> list[dict[str, Any]]:
        rows = self._execute(
            "SELECT id, word_count, overall, xp, created_at FROM submissions WHERE day = ? ORDER BY id",
            (day.isoformat(),),
        )
        return [dict(row) for row in rows]

    def latest_submission(self, day: date) -> dict[str, Any] | None:
        rows = self._execute(
            "SELECT overall, xp, feedback FROM submissions WHERE day = ? ORDER BY id DESC LIMIT 1",
            (day.isoformat(),),
        )
        if not rows:
            return None
        return {"overall": rows[0]["overall"], "xp": rows[0]["xp"], "feedback": json.loads(rows[0]["feedback"])}

    def submitted_days(self) -> set[date]:
        rows = self._execute("SELECT DISTINCT day FROM submissions")
        return {date.fromisoformat(row["day"]) for row in rows}

    def total_xp(self) -> int:
        rows = self._execute(
            "SELECT (SELECT COALESCE(SUM(xp), 0) FROM submissions) + (SELECT COALESCE(SUM(xp), 0) FROM practice) AS xp"
        )
        return int(rows[0]["xp"])

    # Learn practice and unit progress --------------------------------------
    def add_practice(
        self, unit_id: str, task: str, plan: str, draft: str, overall: float, xp: int, feedback: dict
    ) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO practice (unit_id, task, plan, draft, overall, xp, feedback, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (unit_id, task, plan, draft, overall, xp, json.dumps(feedback), _now()),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

    def record_unit_score(self, unit_id: str, overall: float, passed: bool) -> None:
        """Keep the best score per unit; stamp completion the first time a score passes."""
        rows = self._execute("SELECT best_overall, completed_at FROM unit_progress WHERE unit_id = ?", (unit_id,))
        best = max(overall, rows[0]["best_overall"]) if rows else overall
        completed = rows[0]["completed_at"] if rows else None
        if passed and completed is None:
            completed = _now()
        self._execute(
            "INSERT OR REPLACE INTO unit_progress (unit_id, best_overall, completed_at) VALUES (?, ?, ?)",
            (unit_id, best, completed),
        )

    def unit_progress(self) -> dict[str, dict[str, Any]]:
        rows = self._execute("SELECT unit_id, best_overall, completed_at FROM unit_progress")
        return {
            row["unit_id"]: {"best_overall": row["best_overall"], "completed_at": row["completed_at"]}
            for row in rows
        }

    def average_overall(self, limit: int = 10) -> float | None:
        rows = self._execute(
            "SELECT overall FROM submissions ORDER BY id DESC LIMIT ?", (limit,)
        )
        if not rows:
            return None
        return round(sum(row["overall"] for row in rows) / len(rows), 1)

    # Settings -------------------------------------------------------------
    def get_setting(self, key: str, default: str) -> str:
        rows = self._execute("SELECT value FROM settings WHERE key = ?", (key,))
        return rows[0]["value"] if rows else default

    def set_setting(self, key: str, value: str) -> None:
        self._execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


def streak(days: set[date], today: date) -> int:
    """Consecutive submitted days ending today, or yesterday if today is not done yet."""
    cursor = today if today in days else today - timedelta(days=1)
    count = 0
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count
