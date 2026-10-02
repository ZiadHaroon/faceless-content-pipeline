from __future__ import annotations

import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS videos (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    title           TEXT    NOT NULL,
                    stage           TEXT    NOT NULL DEFAULT 'idea',
                    slides_json     TEXT,
                    script_approved INTEGER DEFAULT 0,
                    voiceover_approved INTEGER DEFAULT 0,
                    final_approved  INTEGER DEFAULT 0,
                    platforms       TEXT    DEFAULT '[]',
                    publish_date    TEXT,
                    post_urls       TEXT    DEFAULT '{}',
                    performance     TEXT    DEFAULT '{}',
                    created_at      TEXT    NOT NULL,
                    updated_at      TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS topics (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic      TEXT NOT NULL,
                    tag        TEXT NOT NULL DEFAULT 'other',
                    used       INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS prompts (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       TEXT NOT NULL,
                    template   TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
