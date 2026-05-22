"""Внутренние модели сообщений — adapter-agnostic."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class InternalMessage:
    """Единое представление входящего сообщения от любого адаптера."""
    chat_id: str
    user_id: str
    username: str
    text: str
    image_base64: str | None = None
    is_reply_to_bot: bool = False
    is_mention: bool = False
    raw: Any = None  # оригинальный объект от адаптера


@dataclass
class InternalResponse:
    """Ответ engine для адаптера."""
    text: str
    blocked: bool = False
    warn_message: str | None = None

    @staticmethod
    def sanitize(text: str) -> str:
        """Очистить ответ LLM от XML-подобного мусора (<tool_call...> и т.д.)."""
        # Убрать блоки вида <tool_call...>...</tool_call...>
        text = re.sub(r'<tool_call[^>]*>.*?</tool_call[^>]*>', '', text, flags=re.DOTALL)
        # Убрать прочие XML-подобные теги
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()


@dataclass
class HistoryMessage:
    """Сообщение в истории чата."""
    role: Role
    content: str
    user_name: str | None = None  # для role=user — имя отправителя
