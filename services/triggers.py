"""Триггеры встревания бота в беседу."""

from __future__ import annotations

import logging
import random
import re

from config import ChatConfig

logger = logging.getLogger("triggers")

# Паттерны «вопросов в пустоту»
_QUESTION_PATTERNS = re.compile(
    r"(?:что\s+думаете|как\s+думаете|кто\s+знает|подскажите|"
    r"кто[\s-]нибудь|посоветуйте|есть\s+идеи|как\s+считаете|"
    r"у\s+кого\s+есть|кто\s+может|кто\s+подскажет)",
    re.IGNORECASE,
)


class TriggerService:
    """Определяет, стоит ли боту встрять в разговор."""

    def __init__(self, cfg: ChatConfig):
        self.cfg = cfg
        self._counters: dict[str, int] = {}  # chat_id → count
        self._thresholds: dict[str, int] = {}  # chat_id → random threshold

    def reset_counter(self, chat_id: str) -> None:
        """Сбросить счётчик сообщений для чата."""
        self._counters.pop(chat_id, None)
        self._thresholds.pop(chat_id, None)

    def evaluate(
        self,
        text: str,
        chat_id: str,
        is_bot: bool,
        topics: list[str],
    ) -> tuple[str, str | None] | None:
        """
        Проверить триггеры. Возвращает (trigger_type, topic_matched) или None.
        Считает только сообщения людей (is_bot=False).
        """
        if is_bot:
            return None

        # Приоритет: question > topic > counter
        result = self._check_question(text)
        if result:
            return result

        result = self._check_topics(text, topics)
        if result:
            return result

        return self._check_counter(chat_id)

    def _check_question(self, text: str) -> tuple[str, str | None] | None:
        """Вопросы в пустоту."""
        if _QUESTION_PATTERNS.search(text):
            if random.random() < self.cfg.question_trigger_prob:
                return ("question", None)
        return None

    def _check_topics(self, text: str, topics: list[str]) -> tuple[str, str | None] | None:
        """Упоминание тем из списка."""
        if not topics:
            return None
        text_lower = text.lower()
        for topic in topics:
            if topic.lower() in text_lower:
                if random.random() < self.cfg.topic_trigger_prob:
                    return ("topic", topic)
        return None

    def _check_counter(self, chat_id: str) -> tuple[str, str | None] | None:
        """Счётчик сообщений — после N сообщений встревает."""
        count = self._counters.get(chat_id, 0) + 1
        self._counters[chat_id] = count

        threshold = self._thresholds.get(chat_id)
        if threshold is None:
            threshold = random.randint(self.cfg.counter_min, self.cfg.counter_max)
            self._thresholds[chat_id] = threshold

        if count >= threshold:
            self._counters[chat_id] = 0
            self._thresholds.pop(chat_id, None)
            if random.random() < self.cfg.counter_trigger_prob:
                return ("counter", None)

        return None
