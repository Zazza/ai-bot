"""Ядро обработки сообщений — adapter-agnostic pipeline."""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

from core.models import HistoryMessage, InternalMessage, InternalResponse, Role
from prompts.system import build_system_prompt, build_chatty_hint
from services.triggers import TriggerService

if TYPE_CHECKING:
    from config import AppConfig
    from llm.client import LLMClient
    from services.context import ContextService
    from services.name_match import NameMatcher
    from services.safety import SafetyFilter
    from services.search import SearchService

logger = logging.getLogger("engine")

WATCH_VISION_PROMPT = (
    "Опиши что происходит на этом фото. Фокус только на людях: "
    "категория (ребёнок, девушка, парень, мужчина, женщина), "
    "одежда (цвет, тип), что делают, куда идут. "
    "Не указывай точный возраст — только категорию. "
    "Не описывай здания, мебель, деревья, заборы — только динамика и люди. "
    "Если людей нет — скажи что никого не видно, одним предложением. "
    "Если в подписи к фото указано имя — используй его при описании. "
    "Отвечай коротко и по делу, 1-3 предложения."
)


class Engine:
    """Adapter-agnostic processing pipeline."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.llm: LLMClient | None = None
        self.safety: SafetyFilter | None = None
        self.context: ContextService | None = None
        self.search: SearchService | None = None
        self.name_matcher: NameMatcher | None = None
        self.triggers = TriggerService(config.chat)
        self._rate_counters: dict[str, list[float]] = {}

    def set_services(
        self,
        llm: LLMClient,
        context: ContextService,
        safety: SafetyFilter | None = None,
        search: SearchService | None = None,
        name_matcher: NameMatcher | None = None,
    ):
        self.llm = llm
        self.context = context
        self.safety = safety
        self.search = search
        self.name_matcher = name_matcher

    async def process(self, msg: InternalMessage) -> InternalResponse | None:
        """Обработать сообщение. Возвращает None если бот должен промолчать."""
        cfg = self.config

        # 1. Проверить watch mode для фото
        watch_mode = False
        if msg.image_base64:
            watch_mode = await self.context.get_setting(msg.chat_id, "watch") == "on"

        # 2. Определить, обращаются ли к боту
        addressed = self._is_addressed(msg)
        logger.debug("process: chat=%s addressed=%s watch=%s has_image=%s text=%.80s",
                     msg.chat_id, addressed, watch_mode, bool(msg.image_base64), msg.text or "")

        triggered = None
        if not addressed and not watch_mode:
            # Проверить чатти-режим
            chatty = await self.context.get_setting(msg.chat_id, "chatty")
            if chatty != "on":
                if not cfg.chat.respond_to_all:
                    return None
                if random.random() > cfg.chat.response_probability:
                    return None
            else:
                # Чатти включён — проверить триггеры
                topics = await self.context.get_topics(msg.chat_id, cfg.chat.default_topics)
                triggered = self.triggers.evaluate(
                    text=msg.text or "",
                    chat_id=msg.chat_id,
                    is_bot=msg.user_id == "bot",
                    topics=topics,
                )
                if not triggered:
                    return None
        else:
            # Прямое обращение — сбросить счётчик
            self.triggers.reset_counter(msg.chat_id)

        # 2. Safety check входящего
        if self.safety and cfg.safety.enabled:
            ok, topic = self.safety.check_input(msg.text)
            if not ok:
                logger.warning("Blocked input from %s: topic=%s", msg.user_id, topic)
                return InternalResponse(
                    text="",
                    blocked=True,
                    warn_message=cfg.safety.warn_message,
                )

        # 3. Загрузить контекст
        history = await self.context.load(msg.chat_id, limit=cfg.chat.max_history)

        # 4. Собрать messages для LLM
        system_prompt = build_system_prompt(cfg.personality)
        if triggered:
            trigger_type, topic_matched = triggered
            system_prompt += build_chatty_hint(trigger_type, topic_matched)
        messages = [{"role": "system", "content": system_prompt}]

        for h in history:
            entry: dict = {"role": h.role.value, "content": h.content}
            if h.role == Role.USER and h.user_name:
                entry["content"] = f"{h.user_name}: {h.content}"
            messages.append(entry)

        # Текущее сообщение
        user_content = f"{msg.username}: {msg.text}" if msg.username else msg.text
        messages.append({"role": "user", "content": user_content})

        # 5. LLM вызов (с поиском или без)
        tools = None
        if cfg.llm.tools_enabled and self.search and cfg.search.enabled:
            tools = self.search.get_tools_schema()

        response_text = ""

        if msg.image_base64:
            if watch_mode:
                messages.append({"role": "user", "content": WATCH_VISION_PROMPT})
            response_text = await self.llm.vision(messages, msg.image_base64)
        else:
            response_text = await self._chat_with_tools(messages, tools)

        # 6. Safety check ответа
        if self.safety and cfg.safety.enabled:
            ok, topic = self.safety.check_output(response_text)
            if not ok:
                logger.warning("Blocked output: topic=%s", topic)
                return InternalResponse(
                    text="",
                    blocked=True,
                    warn_message=cfg.safety.warn_message,
                )

        # 7. Сохранить в контекст
        await self.context.save(
            chat_id=msg.chat_id,
            user_id=msg.user_id,
            username=msg.username,
            role=Role.USER,
            content=msg.text,
        )
        await self.context.save(
            chat_id=msg.chat_id,
            user_id="bot",
            username=self.config.personality.name,
            role=Role.ASSISTANT,
            content=response_text,
        )

        return InternalResponse(text=response_text)

    async def _chat_with_tools(self, messages: list[dict], tools: list[dict] | None) -> str:
        """LLM вызов с поддержкой tool calling (поиск)."""
        response = await self.llm.chat(messages, tools=tools)
        msg = response.choices[0]
        logger.info("LLM response: finish_reason=%s content=%s tool_calls=%s",
                     msg.finish_reason,
                     repr(msg.message.content[:200]) if msg.message.content else None,
                     bool(msg.message.tool_calls))

        # Если контент пустой — повторить один раз
        if not msg.message.content:
            logger.warning("Empty LLM response, retrying...")
            response = await self.llm.chat(messages, tools=tools)
            msg = response.choices[0]

        # Если LLM вызвала tool (поиск)
        if msg.finish_reason == "tool_calls" and msg.message.tool_calls:
            for tool_call in msg.message.tool_calls:
                if tool_call.function.name == "web_search":
                    import json
                    args = json.loads(tool_call.function.arguments)
                    query = args.get("query", "")
                    results = await self.search.search(query)

                    # Добавляем результаты поиска в контекст
                    search_content = f"Результаты поиска для «{query}»:\n"
                    for r in results:
                        search_content += f"- {r['title']}: {r['snippet']}\n"

                    messages.append(msg.message.model_dump())
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": search_content,
                    })

                    # Повторный вызов LLM с результатами поиска
                    final = await self.llm.chat(messages, tools=None)
                    return final.choices[0].message.content or ""

        return msg.message.content or ""

    def _is_addressed(self, msg: InternalMessage) -> bool:
        """Проверить, обращаются ли к боту."""
        if msg.is_mention or msg.is_reply_to_bot:
            return True
        if self.name_matcher and msg.text:
            return self.name_matcher.is_addressed(msg.text)
        return False

    def _check_rate_limit(self, user_id: str) -> bool:
        """Rate limit: True если превышен."""
        import time
        now = time.time()
        window = self._rate_counters.setdefault(user_id, [])
        # Очистить старые
        window[:] = [t for t in window if now - t < 60]
        if len(window) >= self.config.chat.rate_limit_per_min:
            return True
        window.append(now)
        return False

    async def clear_context(self, chat_id: str) -> None:
        """Сбросить контекст чата."""
        await self.context.clear(chat_id)
