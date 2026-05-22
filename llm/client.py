"""Универсальный LLM клиент — OpenAI-compatible API."""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

import httpx
from openai import AsyncOpenAI

if TYPE_CHECKING:
    from config import LLMConfig

logger = logging.getLogger("llm")


class LLMClient:
    """Один класс для любого OpenAI-совместимого провайдера."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            http_client=httpx.AsyncClient(proxy=None),
        )
        self.model = config.model
        self.vision_model = config.vision_model

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens_override: int | None = None,
    ):
        """Вызов text модели. Возвращает полный response object."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens_override or self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if tools:
            kwargs["tools"] = tools

        return await self.client.chat.completions.create(**kwargs)

    async def vision(
        self,
        messages: list[dict],
        image_base64: str,
    ) -> str:
        """Вызов vision модели с изображением."""
        # Последнее сообщение — user, добавляем картинку
        last_msg = messages[-1].copy()
        text_content = last_msg.get("content", "")
        last_msg["content"] = [
            {"type": "text", "text": text_content},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}",
                },
            },
        ]

        all_messages = messages[:-1] + [last_msg]

        response = await self.client.chat.completions.create(
            model=self.vision_model,
            messages=all_messages,
            max_tokens=self.config.max_tokens,
        )
        return response.choices[0].message.content or ""
