from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.domain.models import Topic, TopicTag
from src.infrastructure.database import Database
from src.repositories.base import TopicRepository


class SQLiteTopicRepository(TopicRepository):
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_all(self, unused_only: bool = False) -> list[Topic]:
        with self._db.connect() as conn:
            if unused_only:
                rows = conn.execute(
                    "SELECT * FROM topics WHERE used = 0 ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM topics ORDER BY created_at DESC"
                ).fetchall()
        return [self._row_to_topic(r) for r in rows]

    def get_by_id(self, topic_id: int) -> Optional[Topic]:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM topics WHERE id = ?", (topic_id,)
            ).fetchone()
        return self._row_to_topic(row) if row else None

    def create(self, topic: str, tag: TopicTag = TopicTag.other) -> Topic:
        now = datetime.utcnow().isoformat()
        with self._db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO topics (topic, tag, used, created_at) VALUES (?, ?, 0, ?)",
                (topic, tag.value, now),
            )
            topic_id = cur.lastrowid
            conn.commit()
        return self.get_by_id(topic_id)

    def mark_used(self, topic_id: int) -> None:
        with self._db.connect() as conn:
            conn.execute("UPDATE topics SET used = 1 WHERE id = ?", (topic_id,))
            conn.commit()

    def delete(self, topic_id: int) -> None:
        with self._db.connect() as conn:
            conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
            conn.commit()

    @staticmethod
    def _row_to_topic(row) -> Topic:
        d = dict(row)
        return Topic.model_validate({**d, "used": bool(d["used"])})
