"""Базовый класс адаптера — интерфейс для любых фронтендов."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.engine import Engine


class BaseAdapter(ABC):
    """Адаптер связывает фронтенд (Telegram, WebSocket, ...) с Engine."""

    def __init__(self, engine: Engine):
        self.engine = engine

    @abstractmethod
    async def start(self) -> None:
        """Запустить адаптер (начать слушать входящие сообщения)."""

    @abstractmethod
    async def stop(self) -> None:
        """Остановить адаптер."""
