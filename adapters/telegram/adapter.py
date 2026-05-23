"""Telegram адаптер — связывает aiogram с Engine."""

from __future__ import annotations

import base64
import logging
import os
from io import BytesIO
from typing import TYPE_CHECKING

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from adapters.base import BaseAdapter
from core.models import InternalMessage, InternalResponse

if TYPE_CHECKING:
    from config import AppConfig

logger = logging.getLogger("telegram_adapter")


class TelegramAdapter(BaseAdapter):
    """Telegram фронтенд через aiogram 3."""

    def __init__(self, engine, config: AppConfig):
        super().__init__(engine)
        self.config = config

        session = None
        proxy = os.environ.get("TELEGRAM_PROXY")
        if proxy:
            logger.info("Using proxy: %s", proxy)
            session = AiohttpSession(proxy=proxy)

        self.bot = Bot(
            token=config.bot.token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            session=session,
        )
        self.dp = Dispatcher()

        self._bot_username: str | None = None
        self._register_handlers()

    def _register_handlers(self):
        self.dp.message(CommandStart())(self._cmd_start)
        self.dp.message(Command("clear"))(self._cmd_clear)
        self.dp.message(Command("help"))(self._cmd_help)
        self.dp.message(Command("watch"))(self._cmd_watch)
        self.dp.message(Command("chatty"))(self._cmd_chatty)
        self.dp.message()(self._handle_message)

    async def start(self) -> None:
        me = await self.bot.get_me()
        self._bot_username = me.username
        logger.info("Telegram bot started: @%s", me.username)
        await self.dp.start_polling(self.bot)

    async def stop(self) -> None:
        try:
            await self.dp.stop_polling()
        except RuntimeError:
            pass  # Polling wasn't started yet
        await self.bot.session.close()

    # ── Commands ──────────────────────────────────────────────

    async def _cmd_start(self, msg: Message) -> None:
        name = self.config.personality.name
        await msg.answer(f"Привет! Я {name} 👋 Пиши мне что угодно!")

    async def _cmd_clear(self, msg: Message) -> None:
        await self.engine.clear_context(str(msg.chat.id))
        await msg.answer("Контекст сброшен 🧹")

    async def _cmd_help(self, msg: Message) -> None:
        text = (
            "Команды:\n"
            "/clear — сбросить контекст разговора\n"
            "/watch on — анализировать все фото автоматически\n"
            "/watch off — перестать анализировать фото\n"
            "/chatty on — встревать в разговор автоматически\n"
            "/chatty off — отвечать только при обращении\n"
            "/help — эта справка\n\n"
            "Просто напиши моё имя или ответь на моё сообщение!"
        )
        await msg.answer(text)

    async def _cmd_watch(self, msg: Message) -> None:
        text = (msg.text or "").strip().lower()
        chat_id = str(msg.chat.id)

        if text.endswith("on"):
            await self.engine.context.set_setting(chat_id, "watch", "on")
            await msg.answer("Ок, теперь слежу за всеми фото 👀")
        elif text.endswith("off"):
            await self.engine.context.set_setting(chat_id, "watch", "off")
            await msg.answer("Всё, больше не подглядываю 🙈")
        else:
            current = await self.engine.context.get_setting(chat_id, "watch")
            status = "включён 👀" if current == "on" else "выключен"
            await msg.answer(f"Режим наблюдения: {status}\n/watch on — включить\n/watch off — выключить")

    async def _cmd_chatty(self, msg: Message) -> None:
        text = (msg.text or "").strip().lower()
        chat_id = str(msg.chat.id)

        if text.endswith("on"):
            await self.engine.context.set_setting(chat_id, "chatty", "on")
            await msg.answer("Ок, теперь буду встревать в разговор 💬")
        elif text.endswith("off"):
            await self.engine.context.set_setting(chat_id, "chatty", "off")
            await msg.answer("Поняла, буду молчать пока не позовёте 🤐")
        else:
            current = await self.engine.context.get_setting(chat_id, "chatty")
            status = "включён 💬" if current == "on" else "выключен"
            await msg.answer(f"Режим болтушки: {status}\n/chatty on — включить\n/chatty off — выключить")

    # ── Main message handler ──────────────────────────────────

    async def _handle_message(self, msg: Message) -> None:
        if msg.from_user is None:
            return

        # Пропускаем ботов — кроме медиа в watch-режиме
        if msg.from_user.is_bot:
            has_media = msg.photo or msg.animation or msg.video or msg.document
            if not has_media:
                return
            watch = await self.engine.context.get_setting(str(msg.chat.id), "watch")
            logger.debug("Bot message: watch=%s, photo=%s, animation=%s, video=%s, doc=%s, caption=%s",
                         watch, bool(msg.photo), bool(msg.animation), bool(msg.video), bool(msg.document),
                         (msg.caption or "")[:50] if msg.caption else None)
            if watch != "on":
                return
            media_type = "photo" if msg.photo else "animation" if msg.animation else "video" if msg.video else "document"
            logger.info("Bot media in watch mode: %s from %s", media_type, msg.from_user.username or msg.from_user.first_name)

        # Rate limit
        if self.engine._check_rate_limit(str(msg.from_user.id)):
            return

        text = msg.text or msg.caption or ""
        image_base64 = None

        # Скачать фото если есть
        if msg.photo:
            photo = msg.photo[-1]  # самое большое
            file = await self.bot.get_file(photo.file_id)
            buffer = BytesIO()
            await self.bot.download_file(file.file_path, buffer)
            image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        elif msg.animation:
            # GIF / webm — берём thumbnail
            thumb = msg.animation.thumbnail
            if thumb:
                file = await self.bot.get_file(thumb.file_id)
                buffer = BytesIO()
                await self.bot.download_file(file.file_path, buffer)
                image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        elif msg.video:
            # Видео — берём thumbnail
            thumb = msg.video.thumbnail
            if thumb:
                file = await self.bot.get_file(thumb.file_id)
                buffer = BytesIO()
                await self.bot.download_file(file.file_path, buffer)
                image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        elif msg.document and msg.document.thumbnail:
            file = await self.bot.get_file(msg.document.thumbnail.file_id)
            buffer = BytesIO()
            await self.bot.download_file(file.file_path, buffer)
            image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        if not text and not image_base64:
            return

        # Проверить mention/reply
        is_mention = False
        if msg.text:
            is_mention = f"@{self._bot_username}".lower() in msg.text.lower()

        is_reply_to_bot = False
        if msg.reply_to_message:
            reply_user = msg.reply_to_message.from_user
            logger.info("Reply to: from_user=%s bot_id=%s chat=%s",
                        reply_user.id if reply_user else None, self.bot.id, msg.chat.id)
            if reply_user and reply_user.id == self.bot.id:
                is_reply_to_bot = True

        internal = InternalMessage(
            chat_id=str(msg.chat.id),
            user_id=str(msg.from_user.id),
            username=msg.from_user.first_name or msg.from_user.username or "Анон",
            text=text,
            image_base64=image_base64,
            is_reply_to_bot=is_reply_to_bot,
            is_mention=is_mention,
            raw=msg,
        )

        response = await self.engine.process(internal)

        if response is None:
            logger.info("Engine returned None — silent")
            return  # бот решил промолчать

        if response.blocked:
            logger.info("Response blocked by safety")
            if response.warn_message:
                await msg.answer(response.warn_message)
            return

        logger.info("Response text (%d chars): %.200s", len(response.text), response.text)
        if response.text:
            sanitized = InternalResponse.sanitize(response.text)
            logger.info("Sanitized (%d chars): %.200s", len(sanitized), sanitized)
            await msg.answer(sanitized)
        else:
            logger.warning("Empty response text from engine")
