from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from src.domain.models import PipelineStage, Video
from src.infrastructure.database import Database
from src.repositories.base import VideoRepository


class SQLiteVideoRepository(VideoRepository):
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_all(self, stage: Optional[PipelineStage] = None) -> list[Video]:
        with self._db.connect() as conn:
            if stage:
                rows = conn.execute(
                    "SELECT * FROM videos WHERE stage = ? ORDER BY updated_at DESC",
                    (stage.value,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM videos ORDER BY updated_at DESC"
                ).fetchall()
        return [self._row_to_video(r) for r in rows]

    def get_by_id(self, video_id: int) -> Optional[Video]:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM videos WHERE id = ?", (video_id,)
            ).fetchone()
        return self._row_to_video(row) if row else None

    def create(self, title: str, topic_id: Optional[int] = None) -> Video:
        now = datetime.utcnow().isoformat()
        with self._db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO videos (title, stage, slides_json, created_at, updated_at) "
                "VALUES (?, 'idea', '[]', ?, ?)",
                (title, now, now),
            )
            video_id = cur.lastrowid
            if topic_id is not None:
                conn.execute("UPDATE topics SET used = 1 WHERE id = ?", (topic_id,))
            conn.commit()
        return self.get_by_id(video_id)

    def update(self, video: Video) -> Video:
        now = datetime.utcnow().isoformat()
        with self._db.connect() as conn:
            conn.execute(
                """UPDATE videos SET
                    title              = ?,
                    stage              = ?,
                    slides_json        = ?,
                    script_approved    = ?,
                    voiceover_approved = ?,
                    final_approved     = ?,
                    platforms          = ?,
                    publish_date       = ?,
                    post_urls          = ?,
                    performance        = ?,
                    updated_at         = ?
                WHERE id = ?""",
                (
                    video.title,
                    video.stage.value,
                    json.dumps([s.model_dump() for s in video.slides]),
                    int(video.script_approved),
                    int(video.voiceover_approved),
                    int(video.final_approved),
                    json.dumps([p.value for p in video.platforms]),
                    video.publish_date.isoformat() if video.publish_date else None,
                    json.dumps({k.value: v for k, v in video.post_urls.items()}),
                    json.dumps({k.value: v.model_dump() for k, v in video.performance.items()}),
                    now,
                    video.id,
                ),
            )
            conn.commit()
        return self.get_by_id(video.id)

    def delete(self, video_id: int) -> None:
        with self._db.connect() as conn:
            conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
            conn.commit()

    @staticmethod
    def _row_to_video(row) -> Video:
        d = dict(row)
        return Video.model_validate({
            **d,
            "slides":           json.loads(d.get("slides_json") or "[]"),
            "platforms":        json.loads(d.get("platforms") or "[]"),
            "post_urls":        json.loads(d.get("post_urls") or "{}"),
            "performance":      json.loads(d.get("performance") or "{}"),
            "script_approved":  bool(d["script_approved"]),
            "voiceover_approved": bool(d["voiceover_approved"]),
            "final_approved":   bool(d["final_approved"]),
        })
