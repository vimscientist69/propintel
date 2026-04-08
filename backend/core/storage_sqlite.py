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
                    input_path TEXT,
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
                    row_index INTEGER,
                    lead_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_job_id ON leads(job_id);")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_job_row_unique ON leads(job_id, row_index) WHERE row_index IS NOT NULL;"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    batch_index INTEGER NOT NULL,
                    start_row INTEGER NOT NULL,
                    end_row INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    processed_rows INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    UNIQUE(job_id, batch_index)
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_job_batches_job_id ON job_batches(job_id);")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_settings_profiles_active ON settings_profiles(is_active);"
            )
            jobs_cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            if "input_path" not in jobs_cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN input_path TEXT")
            leads_cols = {r["name"] for r in conn.execute("PRAGMA table_info(leads)").fetchall()}
            if "row_index" not in leads_cols:
                conn.execute("ALTER TABLE leads ADD COLUMN row_index INTEGER")
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
    input_path: str | None = None,
) -> None:
    db_path = Path(db_path)
    with _DB_LOCK:
        init_db(db_path)
        conn = _connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO jobs (job_id, status, created_at, input_format, input_path)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, status, _now_iso(), input_format, input_path),
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
                       input_format, input_path, counts_json, rejected_rows_json, error
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
                "input_path": row["input_path"],
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
                       input_format, input_path, counts_json, rejected_rows_json, error
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
                        "input_path": row["input_path"],
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
    row_indices: list[int] | None = None,
) -> None:
    db_path = Path(db_path)
    with _DB_LOCK:
        init_db(db_path)
        conn = _connect(db_path)
        try:
            created_at = _now_iso()
            if row_indices is not None and len(row_indices) != len(leads):
                raise ValueError("row_indices length must match leads length")
            conn.executemany(
                """
                INSERT OR REPLACE INTO leads (job_id, row_index, lead_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        job_id,
                        (row_indices[idx] if row_indices is not None else None),
                        json.dumps(lead, ensure_ascii=False),
                        created_at,
                    )
                    for idx, lead in enumerate(leads)
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


def list_settings_profiles(db_path: str | Path) -> list[dict[str, Any]]:
    db_path = Path(db_path)
    if not db_path.exists():
        return []
    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT name, payload_json, is_active, created_at, updated_at
                FROM settings_profiles
                ORDER BY datetime(updated_at) DESC, id DESC
                """
            ).fetchall()
            return [
                {
                    "name": row["name"],
                    "payload": json.loads(row["payload_json"]),
                    "is_active": bool(row["is_active"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]
        finally:
            conn.close()


def get_active_settings_profile(db_path: str | Path) -> dict[str, Any] | None:
    db_path = Path(db_path)
    if not db_path.exists():
        return None
    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            row = conn.execute(
                """
                SELECT name, payload_json, created_at, updated_at
                FROM settings_profiles
                WHERE is_active = 1
                ORDER BY datetime(updated_at) DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            return {
                "name": row["name"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        finally:
            conn.close()


def upsert_settings_profile(
    db_path: str | Path,
    *,
    name: str,
    payload: dict[str, Any],
    activate: bool = False,
) -> None:
    db_path = Path(db_path)
    with _DB_LOCK:
        init_db(db_path)
        conn = _connect(db_path)
        try:
            now = _now_iso()
            if activate:
                conn.execute("UPDATE settings_profiles SET is_active = 0 WHERE is_active = 1")
            conn.execute(
                """
                INSERT INTO settings_profiles (name, payload_json, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    is_active = CASE WHEN excluded.is_active = 1 THEN 1 ELSE settings_profiles.is_active END,
                    updated_at = excluded.updated_at
                """,
                (name, json.dumps(payload, ensure_ascii=False), 1 if activate else 0, now, now),
            )
            conn.commit()
        finally:
            conn.close()


def activate_settings_profile(db_path: str | Path, *, name: str) -> bool:
    db_path = Path(db_path)
    with _DB_LOCK:
        if not db_path.exists():
            return False
        conn = _connect(db_path)
        try:
            row = conn.execute(
                "SELECT name FROM settings_profiles WHERE name = ?",
                (name,),
            ).fetchone()
            if row is None:
                return False
            conn.execute("UPDATE settings_profiles SET is_active = 0 WHERE is_active = 1")
            conn.execute(
                "UPDATE settings_profiles SET is_active = 1, updated_at = ? WHERE name = ?",
                (_now_iso(), name),
            )
            conn.commit()
            return True
        finally:
            conn.close()


def delete_settings_profile(db_path: str | Path, *, name: str) -> bool:
    db_path = Path(db_path)
    with _DB_LOCK:
        if not db_path.exists():
            return False
        conn = _connect(db_path)
        try:
            row = conn.execute(
                "SELECT name FROM settings_profiles WHERE name = ?",
                (name,),
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                "DELETE FROM settings_profiles WHERE name = ?",
                (name,),
            )
            conn.commit()
            return True
        finally:
            conn.close()


def create_job_batches(
    db_path: str | Path,
    *,
    job_id: str,
    total_rows: int,
    batch_size: int,
) -> None:
    db_path = Path(db_path)
    with _DB_LOCK:
        init_db(db_path)
        conn = _connect(db_path)
        try:
            conn.execute("DELETE FROM job_batches WHERE job_id = ?", (job_id,))
            if total_rows <= 0:
                conn.commit()
                return
            rows = []
            index = 0
            start = 0
            while start < total_rows:
                end = min(total_rows, start + batch_size)
                rows.append((job_id, index, start, end, "pending", 0, None, None, None))
                start = end
                index += 1
            conn.executemany(
                """
                INSERT INTO job_batches (
                    job_id, batch_index, start_row, end_row, status,
                    processed_rows, error, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
        finally:
            conn.close()


def list_job_batches(db_path: str | Path, *, job_id: str) -> list[dict[str, Any]]:
    db_path = Path(db_path)
    if not db_path.exists():
        return []
    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT batch_index, start_row, end_row, status, processed_rows,
                       error, started_at, completed_at
                FROM job_batches
                WHERE job_id = ?
                ORDER BY batch_index ASC
                """,
                (job_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def claim_next_pending_batch(db_path: str | Path, *, job_id: str) -> dict[str, Any] | None:
    db_path = Path(db_path)
    with _DB_LOCK:
        if not db_path.exists():
            return None
        conn = _connect(db_path)
        try:
            row = conn.execute(
                """
                SELECT id, batch_index, start_row, end_row
                FROM job_batches
                WHERE job_id = ? AND status = 'pending'
                ORDER BY batch_index ASC
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                """
                UPDATE job_batches
                SET status = 'processing',
                    started_at = ?,
                    error = NULL
                WHERE id = ?
                """,
                (_now_iso(), row["id"]),
            )
            conn.commit()
            return {
                "batch_index": row["batch_index"],
                "start_row": row["start_row"],
                "end_row": row["end_row"],
            }
        finally:
            conn.close()


def update_job_batch_status(
    db_path: str | Path,
    *,
    job_id: str,
    batch_index: int,
    status: str,
    processed_rows: int = 0,
    error: str | None = None,
) -> None:
    db_path = Path(db_path)
    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            conn.execute(
                """
                UPDATE job_batches
                SET status = ?,
                    processed_rows = ?,
                    error = ?,
                    completed_at = CASE WHEN ? IN ('completed', 'failed', 'terminated') THEN ? ELSE completed_at END
                WHERE job_id = ? AND batch_index = ?
                """,
                (status, processed_rows, error, status, _now_iso(), job_id, batch_index),
            )
            conn.commit()
        finally:
            conn.close()


def reset_resumable_batches(db_path: str | Path, *, job_id: str) -> None:
    db_path = Path(db_path)
    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            conn.execute(
                """
                UPDATE job_batches
                SET status = 'pending',
                    error = NULL,
                    started_at = NULL,
                    completed_at = NULL
                WHERE job_id = ? AND status IN ('failed', 'terminated', 'processing')
                """,
                (job_id,),
            )
            conn.commit()
        finally:
            conn.close()


def summarize_job_batches(db_path: str | Path, *, job_id: str) -> dict[str, int]:
    db_path = Path(db_path)
    if not db_path.exists():
        return {
            "batches_total": 0,
            "batches_started": 0,
            "batches_completed": 0,
            "rows_total": 0,
            "rows_processed": 0,
            "failed_batches": 0,
        }
    with _DB_LOCK:
        conn = _connect(db_path)
        try:
            row = conn.execute(
                """
                SELECT
                    COUNT(1) AS batches_total,
                    SUM(CASE WHEN status IN ('processing', 'completed', 'failed', 'terminated') THEN 1 ELSE 0 END) AS batches_started,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS batches_completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_batches,
                    SUM(end_row - start_row) AS rows_total,
                    SUM(processed_rows) AS rows_processed
                FROM job_batches
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            if row is None:
                return {
                    "batches_total": 0,
                    "batches_started": 0,
                    "batches_completed": 0,
                    "rows_total": 0,
                    "rows_processed": 0,
                    "failed_batches": 0,
                }
            return {
                "batches_total": int(row["batches_total"] or 0),
                "batches_started": int(row["batches_started"] or 0),
                "batches_completed": int(row["batches_completed"] or 0),
                "rows_total": int(row["rows_total"] or 0),
                "rows_processed": int(row["rows_processed"] or 0),
                "failed_batches": int(row["failed_batches"] or 0),
            }
        finally:
            conn.close()

