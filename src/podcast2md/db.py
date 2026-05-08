from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .url_utils import dedupe_key, normalize_url, source_platform


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    platform TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    event_id TEXT,
    message_id TEXT,
    chat_id TEXT,
    sender_id TEXT,
    note TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    output_path TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_created
ON tasks(status, created_at);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def enqueue_url(
    db_path: str | Path,
    url: str,
    *,
    event_id: str | None = None,
    message_id: str | None = None,
    chat_id: str | None = None,
    sender_id: str | None = None,
    note: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[int | None, bool]:
    init_db(db_path)
    url = normalize_url(url)
    now = utc_now()
    key = dedupe_key(url)
    payload = json.dumps(metadata or {}, ensure_ascii=False)
    with connect(db_path) as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO tasks (
                    url, dedupe_key, platform, event_id, message_id, chat_id,
                    sender_id, note, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    url,
                    key,
                    source_platform(url),
                    event_id,
                    message_id,
                    chat_id,
                    sender_id,
                    note,
                    payload,
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid), True
        except sqlite3.IntegrityError:
            row = conn.execute("SELECT id FROM tasks WHERE dedupe_key = ?", (key,)).fetchone()
            return (int(row["id"]) if row else None), False


def claim_next_task(db_path: str | Path) -> sqlite3.Row | None:
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM tasks
            WHERE status IN ('queued', 'retry')
            ORDER BY created_at ASC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return None
        conn.execute(
            """
            UPDATE tasks
            SET status = 'running', attempts = attempts + 1, updated_at = ?
            WHERE id = ?
            """,
            (utc_now(), row["id"]),
        )
        return row


def peek_next_task(db_path: str | Path) -> sqlite3.Row | None:
    init_db(db_path)
    with connect(db_path) as conn:
        return conn.execute(
            """
            SELECT * FROM tasks
            WHERE status IN ('queued', 'retry')
            ORDER BY created_at ASC
            LIMIT 1
            """
        ).fetchone()


def mark_task_success(db_path: str | Path, task_id: int, output_path: str, metadata: dict[str, Any]) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE tasks
            SET status = 'succeeded', output_path = ?, metadata_json = ?,
                last_error = NULL, updated_at = ?
            WHERE id = ?
            """,
            (output_path, json.dumps(metadata, ensure_ascii=False), utc_now(), task_id),
        )


def mark_task_failed(db_path: str | Path, task_id: int, error: str, *, retry: bool = False) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE tasks
            SET status = ?, last_error = ?, updated_at = ?
            WHERE id = ?
            """,
            ("retry" if retry else "failed", error[:4000], utc_now(), task_id),
        )


def retry_task(db_path: str | Path, task_id: int) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE tasks
            SET status = 'retry', last_error = NULL, updated_at = ?
            WHERE id = ?
            """,
            (utc_now(), task_id),
        )


def list_tasks(db_path: str | Path, limit: int = 20) -> list[sqlite3.Row]:
    init_db(db_path)
    with connect(db_path) as conn:
        return list(
            conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        )
