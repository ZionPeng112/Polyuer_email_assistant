from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from email_assistant.config import sqlite_path_from_url
from email_assistant.models import EmailAnalysis, EmailCategory, Importance, RawEmail


class EmailDatabase:
    def __init__(self, database_url: str) -> None:
        self.path = sqlite_path_from_url(database_url)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "EmailDatabase":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def initialize(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                message_id TEXT,
                subject TEXT NOT NULL,
                sender TEXT NOT NULL,
                recipients_json TEXT NOT NULL,
                received_for_json TEXT NOT NULL,
                created_at TEXT,
                body_sha256 TEXT,
                attachments_json TEXT NOT NULL,
                html_images_json TEXT NOT NULL DEFAULT '[]',
                inserted_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analyses (
                email_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                importance TEXT NOT NULL,
                summary TEXT NOT NULL,
                mandatory INTEGER NOT NULL,
                action_required INTEGER NOT NULL,
                action TEXT,
                deadline TEXT,
                event_time TEXT,
                location TEXT,
                evidence TEXT,
                confidence REAL NOT NULL,
                analysis_json TEXT NOT NULL,
                analyzed_at TEXT NOT NULL,
                FOREIGN KEY(email_id) REFERENCES emails(id)
            );

            CREATE INDEX IF NOT EXISTS idx_emails_created_at ON emails(created_at);
            CREATE INDEX IF NOT EXISTS idx_analyses_category ON analyses(category);
            """
        )
        self._ensure_column("emails", "html_images_json", "TEXT NOT NULL DEFAULT '[]'")
        self._conn.commit()

    def is_processed(self, email_id: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM analyses WHERE email_id = ?", (email_id,)).fetchone()
        return row is not None

    def delete_analysis(self, email_id: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM analyses WHERE email_id = ?", (email_id,))

    def save_email_analysis(
        self,
        *,
        email: RawEmail,
        clean_text: str,
        analysis: EmailAnalysis,
        html_images: list[object] | None = None,
    ) -> None:
        now = _utc_now()
        attachments = [_jsonable_dataclass(item) for item in email.attachments]
        html_image_rows = [_jsonable_dataclass(item) for item in html_images or []]
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO emails (
                    id, message_id, subject, sender, recipients_json, received_for_json,
                    created_at, body_sha256, attachments_json, html_images_json, inserted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email.id,
                    email.message_id,
                    email.subject,
                    email.sender,
                    json.dumps(email.to, ensure_ascii=False),
                    json.dumps(email.received_for, ensure_ascii=False),
                    email.created_at.isoformat() if email.created_at else None,
                    hashlib.sha256(clean_text.encode("utf-8")).hexdigest(),
                    json.dumps(attachments, ensure_ascii=False),
                    json.dumps(html_image_rows, ensure_ascii=False),
                    now,
                ),
            )
            self._conn.execute(
                """
                INSERT OR REPLACE INTO analyses (
                    email_id, category, importance, summary, mandatory, action_required,
                    action, deadline, event_time, location, evidence, confidence,
                    analysis_json, analyzed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis.email_id,
                    analysis.category.value,
                    analysis.importance.value,
                    analysis.summary,
                    int(analysis.mandatory),
                    int(analysis.action_required),
                    analysis.action,
                    analysis.deadline,
                    analysis.event_time,
                    analysis.location,
                    analysis.evidence,
                    analysis.confidence,
                    json.dumps(analysis.to_dict(), ensure_ascii=False),
                    now,
                ),
            )

    def list_recent_analyses(self, *, since: datetime | None = None) -> list[EmailAnalysis]:
        query = """
            SELECT analyses.*, emails.subject
            FROM analyses
            JOIN emails ON emails.id = analyses.email_id
        """
        params: tuple[Any, ...] = ()
        if since is not None:
            query += " WHERE emails.created_at IS NULL OR emails.created_at >= ?"
            params = (since.isoformat(),)
        query += " ORDER BY emails.created_at DESC, analyses.analyzed_at DESC"

        rows = self._conn.execute(query, params).fetchall()
        return [_analysis_from_row(row) for row in rows]

    def list_analyses_between(self, *, start: datetime, end: datetime) -> list[EmailAnalysis]:
        rows = self._conn.execute(
            """
            SELECT analyses.*, emails.subject
            FROM analyses
            JOIN emails ON emails.id = analyses.email_id
            WHERE emails.created_at >= ? AND emails.created_at < ?
            ORDER BY emails.created_at DESC, analyses.analyzed_at DESC
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [_analysis_from_row(row) for row in rows]

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        if any(row["name"] == column for row in rows):
            return
        self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _analysis_from_row(row: sqlite3.Row) -> EmailAnalysis:
    return EmailAnalysis(
        email_id=row["email_id"],
        category=EmailCategory(row["category"]),
        importance=Importance(row["importance"]),
        summary=row["summary"],
        mandatory=bool(row["mandatory"]),
        action_required=bool(row["action_required"]),
        action=row["action"],
        deadline=row["deadline"],
        event_time=row["event_time"],
        location=row["location"],
        evidence=row["evidence"],
        confidence=float(row["confidence"]),
        subject=row["subject"] if "subject" in row.keys() else None,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable_dataclass(value: object) -> dict[str, Any]:
    data = asdict(value)
    for key, item in list(data.items()):
        if isinstance(item, datetime):
            data[key] = item.isoformat()
    return data
