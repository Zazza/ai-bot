"""CLI адаптер — интерактивный REPL для тестирования."""

from __future__ import annotations

import asyncio
import sys

from adapters.base import BaseAdapter
from core.models import InternalMessage


class CLIAdapter(BaseAdapter):
    """Простой REPL в терминале."""

    def __init__(self, engine, config):
        super().__init__(engine)
        self.config = config
        self.chat_id = "cli"
        self.user_id = "user"
        self.username = "Ты"

    async def start(self) -> None:
        name = self.config.personality.name
        print(f"\n=== {name} (CLI mode) ===")
        print("Введи /clear для сброса контекста, /quit для выхода\n")

        loop = asyncio.get_event_loop()

        while True:
            try:
                text = await loop.run_in_executor(None, lambda: input("Ты: "))
            except (EOFError, KeyboardInterrupt):
                break

            text = text.strip()
            if not text:
                continue

            if text == "/quit":
                break

            if text == "/clear":
                await self.engine.clear_context(self.chat_id)
                print(f"{name}: Контекст сброшен 🧹\n")
                continue

            msg = InternalMessage(
                chat_id=self.chat_id,
                user_id=self.user_id,
                username=self.username,
                text=text,
                is_mention=True,  # в CLI всё — обращение к боту
            )

            response = await self.engine.process(msg)

            if response is None:
                continue

            if response.blocked:
                if response.warn_message:
                    print(f"{name}: {response.warn_message}\n")
                continue

            if response.text:
                print(f"{name}: {response.text}\n")

    async def stop(self) -> None:
        pass
