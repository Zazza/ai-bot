"""Гибридный safety-фильтр: keywords + LLM fallback."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import AppConfig

logger = logging.getLogger("safety")

# Ключевые слова по темам
SAFETY_KEYWORDS: dict[str, list[str]] = {
    "violence": ["убить", "убей", "ударить", "изби", "кровь", "расправ", "пытк",
                 "зверски", "калеч", "задуш", "зарез", "отрав"],
    "weapons": ["оружие", "пистолет", "нож", "гранат", "бомб", "винтовк", "автомат",
                "патрон", "обрез", "травмат", "газовый баллончик"],
    "drugs": ["наркотик", "косяк", "травк", "гашиш", "кокаин", "героин", "спайс",
              "амфетамин", "экстази", "лсд", "марихуан", "метадон", "барыга"],
    "suicide": ["суицид", "покончить с собой", "убить себя", "не хочу жить",
                "прыгнуть с", "повеситься", "вскрыть вены", "свести счёты"],
    "sexual_content": ["порн", "секс", "обнажен", "интим", "раздев", "голая",
                       "голый", "проститу", "эрот", "стрипптиз"],
    "extremism": ["террор", "экстрем", "радикал", "бомбить", "шахид", "джихад"],
    "self_harm": ["порезать", "навредить себе", "самоповрежд", "больно себе",
                  "резать вены", "ожог себе"],
    "gambling": ["ставк", "казино", "букмекер", "беттинг", "азартн", "тотализатор"],
    "alcohol": ["водк", "пив", "вино", "выпивк", "спиртн", "алкогол", "коньяк",
                "виски", "ром", "джин", "шампанск"],
    "smoking": ["сигарет", "курить", "вейп", "кальян", "табак", "электронн"],
}


class SafetyFilter:
    """Двухэтапный safety-фильтр: keywords (быстро) + LLM (пограничные)."""

    def __init__(self, config: AppConfig, llm_client=None):
        self.config = config
        self.llm = llm_client
        self._keywords = self._build_keywords()

    def _build_keywords(self) -> dict[str, list[str]]:
        """Собрать итоговый словарь ключевых слов с учётом конфига."""
        keywords = {}
        allowed = set(self.config.safety.custom_allowed)

        for topic, words in SAFETY_KEYWORDS.items():
            if topic in allowed:
                continue
            if topic in self.config.safety.forbidden_topics:
                keywords[topic] = words[:]

        # Добавить кастомные
        for item in self.config.safety.custom_blocked:
            if isinstance(item, dict):
                topic = item.get("topic", "custom")
                words = item.get("words", [])
                keywords.setdefault(topic, []).extend(words)
            else:
                keywords.setdefault("custom", []).append(item)

        return keywords

    def check_input(self, text: str) -> tuple[bool, str | None]:
        """Проверить входящее сообщение. (ok, topic)"""
        if not text:
            return True, None
        return self._keyword_check(text)

    def check_output(self, text: str) -> tuple[bool, str | None]:
        """Проверить ответ бота. (ok, topic)"""
        if not text:
            return True, None
        return self._keyword_check(text)

    def _keyword_check(self, text: str) -> tuple[bool, str | None]:
        """Keyword check — быстрый, без LLM."""
        lower = text.lower()
        for topic, words in self._keywords.items():
            for word in words:
                if word in lower:
                    return False, topic
        return True, None

    async def _llm_check(self, text: str, topic: str) -> bool:
        """LLM check для пограничных случаев. True = безопасно."""
        if not self.llm:
            return False

        prompt = (
            f"Определи, содержит ли это сообщение тему '{topic}'. "
            f"Ответь ТОЛЬКО YES или NO.\n\nСообщение: {text}"
        )
        try:
            response = await self.llm.chat(
                [{"role": "user", "content": prompt}],
                tools=None,
                max_tokens_override=10,
            )
            answer = response.choices[0].message.content.strip().upper()
            return answer != "YES"
        except Exception as e:
            logger.error("LLM safety check failed: %s", e)
            return False  # при ошибке — блокируем
