"""Telegram адаптер — связывает aiogram с Engine."""

from __future__ import annotations

import base64
import logging
import os
from io import BytesIO
from typing import TYPE_CHECKING

import aiohttp
from aiohttp_socks import ProxyConnector
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession as _AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from adapters.base import BaseAdapter
from core.models import InternalMessage, InternalResponse

if TYPE_CHECKING:
    from config import AppConfig

logger = logging.getLogger("telegram_adapter")


class SocksSession(_AiohttpSession):
    """AiohttpSession с поддержкой SOCKS5 через ProxyConnector."""

    def __init__(self, proxy_url: str):
        super().__init__()
        self._proxy_url = proxy_url

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._connector = ProxyConnector.from_url(self._proxy_url)
            self._session = aiohttp.ClientSession(connector=self._connector)
        return self._session


class TelegramAdapter(BaseAdapter):
    """Telegram фронтенд через aiogram 3."""

    def __init__(self, engine, config: AppConfig):
        super().__init__(engine)
        self.config = config

        session = None
        proxy = os.environ.get("TELEGRAM_PROXY")
        if proxy:
            logger.info("Using proxy: %s", proxy)
            session = SocksSession(proxy)

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
        self.dp.message()(self._handle_message)

    async def start(self) -> None:
        me = await self.bot.get_me()
        self._bot_username = me.username
        logger.info("Telegram bot started: @%s", me.username)
        await self.dp.start_polling(self.bot)

    async def stop(self) -> None:
        await self.dp.stop_polling()
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
            "/help — эта справка\n\n"
            "Просто напиши моё имя или ответь на моё сообщение!"
        )
        await msg.answer(text)

    # ── Main message handler ──────────────────────────────────

    async def _handle_message(self, msg: Message) -> None:
        if msg.from_user is None or msg.from_user.is_bot:
            return

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

        if not text and not image_base64:
            return

        # Проверить mention/reply
        is_mention = False
        if msg.text:
            is_mention = f"@{self._bot_username}".lower() in msg.text.lower()

        is_reply_to_bot = False
        if msg.reply_to_message and msg.reply_to_message.from_user:
            is_reply_to_bot = msg.reply_to_message.from_user.id == self.bot.id

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
            return  # бот решил промолчать

        if response.blocked:
            if response.warn_message:
                await msg.answer(response.warn_message)
            return

        if response.text:
            await msg.answer(response.text)
