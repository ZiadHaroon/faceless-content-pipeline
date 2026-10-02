import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "data" / "pipeline.db"

SEED_TOPICS = [
    ("How does Face ID actually work", "device"),
    ("Why does your phone battery degrade over time", "device"),
    ("What is a VPN actually doing", "security"),
    ("How AI image generators actually draw", "AI"),
    ("Why 5G isn't as big a deal as advertised", "internet"),
    ("How does end-to-end encryption work", "security"),
    ("What happens when you delete a file", "device"),
    ("Why does your phone get hot when charging", "device"),
    ("How do noise-cancelling headphones work", "device"),
    ("What is quantum computing actually trying to solve", "AI"),
]

SEED_PROMPT_NAME = "Default Script Template"
SEED_PROMPT_TEMPLATE = (
    "You are writing a 45-60 second YouTube Shorts script about [TOPIC].\n"
    "Structure: (1) a hook in the first 8 words that creates curiosity or states something surprising, "
    "(2) 3 concise points building on each other, "
    "(3) a punchy closer or open question. "
    "Plain, spoken English, no jargon unless explained. ~150 words total."
)


def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            stage TEXT NOT NULL DEFAULT 'idea',
            script_json TEXT,
            script_approved INTEGER DEFAULT 0,
            voiceover_path TEXT,
            voiceover_approved INTEGER DEFAULT 0,
            assembly_path TEXT,
            final_approved INTEGER DEFAULT 0,
            platforms TEXT,
            publish_date TEXT,
            post_urls TEXT DEFAULT '{}',
            performance TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            tag TEXT DEFAULT '',
            used INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            template TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()

    # Seed topics if empty
    cur.execute("SELECT COUNT(*) FROM topics")
    if cur.fetchone()[0] == 0:
        now = datetime.utcnow().isoformat()
        for topic, tag in SEED_TOPICS:
            cur.execute(
                "INSERT INTO topics (topic, tag, used, created_at) VALUES (?, ?, 0, ?)",
                (topic, tag, now),
            )
        conn.commit()

    # Seed default prompt if empty
    cur.execute("SELECT COUNT(*) FROM prompts")
    if cur.fetchone()[0] == 0:
        now = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO prompts (name, template, created_at) VALUES (?, ?, ?)",
            (SEED_PROMPT_NAME, SEED_PROMPT_TEMPLATE, now),
        )
        conn.commit()

    conn.close()


# ── Videos ──────────────────────────────────────────────────────────────────

def get_videos(stage=None):
    conn = _get_conn()
    cur = conn.cursor()
    if stage:
        cur.execute(
            "SELECT * FROM videos WHERE stage = ? ORDER BY updated_at DESC", (stage,)
        )
    else:
        cur.execute("SELECT * FROM videos ORDER BY updated_at DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_video(video_id):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def create_video(title, topic_id=None):
    now = datetime.utcnow().isoformat()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO videos (title, stage, created_at, updated_at) VALUES (?, 'idea', ?, ?)",
        (title, now, now),
    )
    video_id = cur.lastrowid
    if topic_id is not None:
        cur.execute("UPDATE topics SET used = 1 WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()
    return video_id


def update_video(video_id, **kwargs):
    if not kwargs:
        return
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [video_id]
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE videos SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_video(video_id):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM videos WHERE id = ?", (video_id,))
    conn.commit()
    conn.close()


# ── Topics ───────────────────────────────────────────────────────────────────

def get_topics(unused_only=False):
    conn = _get_conn()
    cur = conn.cursor()
    if unused_only:
        cur.execute(
            "SELECT * FROM topics WHERE used = 0 ORDER BY created_at DESC"
        )
    else:
        cur.execute("SELECT * FROM topics ORDER BY created_at DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def add_topic(topic, tag=""):
    now = datetime.utcnow().isoformat()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO topics (topic, tag, used, created_at) VALUES (?, ?, 0, ?)",
        (topic, tag, now),
    )
    conn.commit()
    conn.close()


def mark_topic_used(topic_id):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE topics SET used = 1 WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()


def delete_topic(topic_id):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()


# ── Prompts ──────────────────────────────────────────────────────────────────

def get_prompts():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM prompts ORDER BY created_at DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def add_prompt(name, template):
    now = datetime.utcnow().isoformat()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO prompts (name, template, created_at) VALUES (?, ?, ?)",
        (name, template, now),
    )
    conn.commit()
    conn.close()


def delete_prompt(prompt_id):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
    conn.commit()
    conn.close()
