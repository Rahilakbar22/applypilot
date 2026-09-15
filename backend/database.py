"""
A tiny SQLite-backed application tracker - the "mini-ATS" that remembers
every job you've saved or prepared an application for, and lets you move it
through a status pipeline as you actually apply, hear back, and interview.

Deliberately plain sqlite3 (no ORM) to keep the project dependency-light and
the schema easy to read in one glance.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "applypilot.db"

VALID_STATUSES = ["saved", "prepared", "applied", "interviewing", "offer", "rejected"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracked_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    url TEXT,
    match_score REAL,
    status TEXT NOT NULL DEFAULT 'saved',
    cover_letter TEXT,
    notes TEXT DEFAULT '',
    job_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(SCHEMA)

def upsert_tracked_job(job: dict, status: str = "saved", cover_letter: str | None = None) -> dict:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}.")
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM tracked_jobs WHERE job_id = ?", (job["id"],)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE tracked_jobs
                   SET status = ?, cover_letter = COALESCE(?, cover_letter),
                       match_score = COALESCE(?, match_score),
                       updated_at = CURRENT_TIMESTAMP
                   WHERE job_id = ?""",
                (status, cover_letter, job.get("match_score"), job["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO tracked_jobs
                   (job_id, title, company, location, url, match_score, status, cover_letter, job_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job["id"], job["title"], job["company"], job.get("location", ""),
                    job.get("url", ""), job.get("match_score"), status, cover_letter,
                    json.dumps(job),
                ),
            )
        row = conn.execute("SELECT * FROM tracked_jobs WHERE job_id = ?", (job["id"],)).fetchone()
        return dict(row)


def update_status(job_id: str, status: str, notes: str | None = None) -> dict | None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}.")
    with get_conn() as conn:
        conn.execute(
            """UPDATE tracked_jobs
               SET status = ?, notes = COALESCE(?, notes), updated_at = CURRENT_TIMESTAMP
               WHERE job_id = ?""",
            (status, notes, job_id),
        )
        row = conn.execute("SELECT * FROM tracked_jobs WHERE job_id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def list_tracked_jobs() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tracked_jobs ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_tracked_job(job_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM tracked_jobs WHERE job_id = ?", (job_id,))
        return cur.rowcount > 0

