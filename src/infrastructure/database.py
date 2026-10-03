from __future__ import annotations

import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._shared_conn: sqlite3.Connection | None = None

        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        # In-memory databases must reuse one connection — each new connection
        # gets a completely separate empty database.
        if self._path == ":memory:":
            if self._shared_conn is None:
                self._shared_conn = self._make_conn()
            return self._shared_conn

        return self._make_conn()

    def _make_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        if self._path != ":memory:":
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
            # Add v2 columns to videos if upgrading from v1 schema
            self._add_column_if_missing(conn, "videos", "slides_json", "TEXT")
            self._add_column_if_missing(conn, "videos", "script_approved", "INTEGER DEFAULT 0")
            self._add_column_if_missing(conn, "videos", "voiceover_approved", "INTEGER DEFAULT 0")
            self._add_column_if_missing(conn, "videos", "final_approved", "INTEGER DEFAULT 0")
            self._add_column_if_missing(conn, "videos", "platforms", "TEXT DEFAULT '[]'")
            self._add_column_if_missing(conn, "videos", "publish_date", "TEXT")
            self._add_column_if_missing(conn, "videos", "post_urls", "TEXT DEFAULT '{}'")
            self._add_column_if_missing(conn, "videos", "performance", "TEXT DEFAULT '{}'")

    @staticmethod
    def _add_column_if_missing(
        conn: sqlite3.Connection, table: str, column: str, definition: str
    ) -> None:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
