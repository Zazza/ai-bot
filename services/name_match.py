"""Распознавание обращения к боту по имени."""

from __future__ import annotations

import re

from rapidfuzz import fuzz


class NameMatcher:
    """Матчит имя бота и его производные в тексте."""

    def __init__(self, name_patterns: list[str]):
        self.name_patterns = [p.lower() for p in name_patterns]

    def is_addressed(self, text: str) -> bool:
        """Проверить, обращаются ли к боту в данном тексте."""
        normalized = re.sub(r'[^\w\s@]', '', text.lower())
        words = normalized.split()

        for word in words:
            # Prefix match: "маш" matches "маша", "машка"
            for pattern in self.name_patterns:
                if word.startswith(pattern) or pattern.startswith(word):
                    return True

            # Fuzzy match для опечаток
            if len(word) >= 3:
                for pattern in self.name_patterns:
                    if fuzz.ratio(word, pattern) >= 80:
                        return True

        return False
