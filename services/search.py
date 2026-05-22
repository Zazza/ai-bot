"""Веб-поиск через SearXNG — отключаемый компонент."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from config import AppConfig

logger = logging.getLogger("search")

# OpenAI function calling schema для поиска
SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Ищи информацию в интернете. Используй когда нужно найти: "
            "актуальные данные, погоду, новости, цены, товары, факты. "
            "Формулируй поисковый запрос кратко и точно."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос (например: 'погода Москва сегодня' или 'чёрная майка Ozon')",
                }
            },
            "required": ["query"],
        },
    },
}


class SearchService:
    """SearXNG клиент для веб-поиска."""

    def __init__(self, config: AppConfig):
        self.url = config.search.searxng_url.rstrip("/")
        self.language = config.search.language
        self.max_results = config.search.max_results
        self._session: aiohttp.ClientSession | None = None

    async def init(self) -> None:
        self._session = aiohttp.ClientSession()
        logger.info("Search service initialized (SearXNG: %s)", self.url)

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    def get_tools_schema(self) -> list[dict]:
        """Вернуть OpenAI tools schema для function calling."""
        return [SEARCH_TOOL_SCHEMA]

    async def search(self, query: str) -> list[dict]:
        """Выполнить поиск через SearXNG. Возвращает list[{title, snippet, url}]."""
        if not self._session:
            return []

        params = {
            "q": query,
            "format": "json",
            "language": self.language,
        }

        try:
            async with self._session.get(
                f"{self.url}/search", params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    logger.error("SearXNG returned %s", resp.status)
                    return []

                data = await resp.json()
                results = data.get("results", [])[:self.max_results]

                return [
                    {
                        "title": r.get("title", ""),
                        "snippet": r.get("content", ""),
                        "url": r.get("url", ""),
                    }
                    for r in results
                ]
        except Exception as e:
            logger.error("Search failed: %s", e)
            return []
