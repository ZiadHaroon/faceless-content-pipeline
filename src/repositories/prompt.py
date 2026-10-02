from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.domain.models import Prompt
from src.infrastructure.database import Database
from src.repositories.base import PromptRepository


class SQLitePromptRepository(PromptRepository):
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_all(self) -> list[Prompt]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM prompts ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_prompt(r) for r in rows]

    def get_by_id(self, prompt_id: int) -> Optional[Prompt]:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM prompts WHERE id = ?", (prompt_id,)
            ).fetchone()
        return self._row_to_prompt(row) if row else None

    def create(self, name: str, template: str) -> Prompt:
        now = datetime.utcnow().isoformat()
        with self._db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO prompts (name, template, created_at) VALUES (?, ?, ?)",
                (name, template, now),
            )
            prompt_id = cur.lastrowid
            conn.commit()
        return self.get_by_id(prompt_id)

    def delete(self, prompt_id: int) -> None:
        with self._db.connect() as conn:
            conn.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
            conn.commit()

    @staticmethod
    def _row_to_prompt(row) -> Prompt:
        return Prompt.model_validate(dict(row))
