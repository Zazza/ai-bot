"""Управление контекстом чата через SQLite (aiosqlite)."""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from core.models import HistoryMessage, Role

logger = logging.getLogger("context")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    username TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp REAL NOT NULL DEFAULT (strftime('%s','now'))
)
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_messages_chat_ts
ON messages(chat_id, timestamp)
"""


class ContextService:
    """Хранение истории чата в SQLite."""

    def __init__(self, db_path: str = "data/context.db"):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        """Инициализировать БД."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute(CREATE_TABLE_SQL)
        await self._db.execute(CREATE_INDEX_SQL)
        await self._db.commit()
        logger.info("Context DB initialized: %s", self.db_path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def save(
        self,
        chat_id: str,
        user_id: str,
        username: str | None,
        role: Role,
        content: str,
    ) -> None:
        """Сохранить сообщение в историю."""
        await self._db.execute(
            "INSERT INTO messages (chat_id, user_id, username, role, content) VALUES (?, ?, ?, ?, ?)",
            (chat_id, user_id, username, role.value, content),
        )
        await self._db.commit()

    async def load(self, chat_id: str, limit: int = 50) -> list[HistoryMessage]:
        """Загрузить последние N сообщений чата."""
        cursor = await self._db.execute(
            "SELECT role, content, username FROM messages "
            "WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ?",
            (chat_id, limit),
        )
        rows = await cursor.fetchall()
        # Разворачиваем — от старых к новым
        rows = list(reversed(rows))

        return [
            HistoryMessage(
                role=Role(row[0]),
                content=row[1],
                user_name=row[2],
            )
            for row in rows
        ]

    async def clear(self, chat_id: str) -> None:
        """Очистить контекст чата."""
        await self._db.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        await self._db.commit()
        logger.info("Context cleared for chat %s", chat_id)
