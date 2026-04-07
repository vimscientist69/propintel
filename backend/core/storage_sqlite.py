from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


_DB_LOCK = threading.RLock()


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Prefer WAL for concurrent reads while one writer is active.
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db(db_path: str | Path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    input_format TEXT,
                    counts_json TEXT,
                    rejected_rows_json TEXT,
                    error TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    lead_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_job_id ON leads(job_id);")
            conn.commit()
        finally:
            conn.close()


def _now_iso() -> str:
    return datetime.now().isoformat()


def create_job(
    db_path: str | Path,
    *,
    job_id: str,
    input_format: str,
    status: str,
) -> None:
    db_path = Path(db_path)
    with _DB_LOCK:
        init_db(db_path)
        conn = _connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO jobs (job_id, status, created_at, input_format)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, status, _now_iso(), input_format),
            )
            conn.commit()
        finally:
            conn.close()


def update_job_processing_started(
    db_path: str | Path,
    *,
    job_id: str,
) -> None:
    db_path = Path(db_path)
    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    started_at = ?
                WHERE job_id = ?
                """,
                ("processing", _now_iso(), job_id),
            )
            conn.commit()
        finally:
            conn.close()


def update_job_completed(
    db_path: str | Path,
    *,
    job_id: str,
    counts: dict[str, Any],
    rejected_rows: list[dict[str, Any]],
) -> None:
    db_path = Path(db_path)
    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    completed_at = ?,
                    counts_json = ?,
                    rejected_rows_json = ?,
                    error = NULL
                WHERE job_id = ?
                """,
                (
                    "completed",
                    _now_iso(),
                    json.dumps(counts, ensure_ascii=False),
                    json.dumps(rejected_rows, ensure_ascii=False),
                    job_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def update_job_failed(
    db_path: str | Path,
    *,
    job_id: str,
    error: str,
) -> None:
    db_path = Path(db_path)
    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    completed_at = ?,
                    error = ?
                WHERE job_id = ?
                """,
                ("failed", _now_iso(), error, job_id),
            )
            conn.commit()
        finally:
            conn.close()


def update_job_terminated(
    db_path: str | Path,
    *,
    job_id: str,
    error: str = "terminated_by_user",
) -> None:
    db_path = Path(db_path)
    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    completed_at = ?,
                    error = ?
                WHERE job_id = ?
                """,
                ("terminated", _now_iso(), error, job_id),
            )
            conn.commit()
        finally:
            conn.close()


def get_job(db_path: str | Path, *, job_id: str) -> dict[str, Any] | None:
    db_path = Path(db_path)
    if not db_path.exists():
        return None

    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            row = conn.execute(
                """
                SELECT job_id, status, created_at, started_at, completed_at,
                       input_format, counts_json, rejected_rows_json, error
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

            if row is None:
                return None

            counts = json.loads(row["counts_json"]) if row["counts_json"] else None
            rejected_rows = (
                json.loads(row["rejected_rows_json"]) if row["rejected_rows_json"] else None
            )
            return {
                "job_id": row["job_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "input_format": row["input_format"],
                "counts": counts,
                "rejected_rows": rejected_rows,
                "error": row["error"],
            }
        finally:
            conn.close()


def list_jobs(
    db_path: str | Path,
    *,
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    db_path = Path(db_path)
    if not db_path.exists():
        return [], 0

    safe_limit = max(1, min(100, int(limit)))
    safe_offset = max(0, int(offset))
    normalized_status = (status or "").strip()

    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            where_sql = ""
            where_params: tuple[Any, ...] = ()
            if normalized_status:
                where_sql = "WHERE status = ?"
                where_params = (normalized_status,)

            total_row = conn.execute(
                f"SELECT COUNT(1) AS total FROM jobs {where_sql}",
                where_params,
            ).fetchone()
            total = int(total_row["total"]) if total_row is not None else 0

            rows = conn.execute(
                f"""
                SELECT job_id, status, created_at, started_at, completed_at,
                       input_format, counts_json, rejected_rows_json, error
                FROM jobs
                {where_sql}
                ORDER BY datetime(created_at) DESC, job_id DESC
                LIMIT ? OFFSET ?
                """,
                (*where_params, safe_limit, safe_offset),
            ).fetchall()

            items: list[dict[str, Any]] = []
            for row in rows:
                counts = json.loads(row["counts_json"]) if row["counts_json"] else None
                rejected_rows = (
                    json.loads(row["rejected_rows_json"]) if row["rejected_rows_json"] else None
                )
                items.append(
                    {
                        "job_id": row["job_id"],
                        "status": row["status"],
                        "created_at": row["created_at"],
                        "started_at": row["started_at"],
                        "completed_at": row["completed_at"],
                        "input_format": row["input_format"],
                        "counts": counts,
                        "rejected_rows": rejected_rows,
                        "error": row["error"],
                    }
                )
            return items, total
        finally:
            conn.close()


def insert_leads(
    db_path: str | Path,
    *,
    job_id: str,
    leads: list[dict[str, Any]],
) -> None:
    db_path = Path(db_path)
    with _DB_LOCK:
        init_db(db_path)
        conn = _connect(db_path)
        try:
            created_at = _now_iso()
            conn.executemany(
                """
                INSERT INTO leads (job_id, lead_json, created_at)
                VALUES (?, ?, ?)
                """,
                [
                    (job_id, json.dumps(lead, ensure_ascii=False), created_at)
                    for lead in leads
                ],
            )
            conn.commit()
        finally:
            conn.close()


def get_leads(db_path: str | Path, *, job_id: str) -> list[dict[str, Any]]:
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            rows = conn.execute(
                "SELECT lead_json FROM leads WHERE job_id = ? ORDER BY id ASC",
                (job_id,),
            ).fetchall()
            return [json.loads(r["lead_json"]) for r in rows]
        finally:
            conn.close()

