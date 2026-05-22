"""HTTP API server — приём фото/сообщений от внешних систем (HA/Frigate)."""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

from aiohttp import web

from core.models import InternalMessage, InternalResponse

if TYPE_CHECKING:
    from aiogram import Bot
    from config import AppConfig
    from core.engine import Engine

logger = logging.getLogger("api")


def create_app(config: AppConfig, engine: Engine, bot: Bot) -> web.Application:
    """Создать aiohttp Application с API endpoint."""
    app = web.Application()
    app["config"] = config
    app["engine"] = engine
    app["bot"] = bot
    app.router.add_post("/api/send", _handle_send)
    return app


async def _handle_send(request: web.Request) -> web.Response:
    config: AppConfig = request.app["config"]
    engine: Engine = request.app["engine"]
    bot: Bot = request.app["bot"]

    # 1. Auth
    expected = config.api.token
    if expected:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {expected}":
            return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    # 2. Read multipart fields
    try:
        reader = await request.multipart()
        chat_id = None
        text = ""
        photo_bytes = None

        while part := await reader.next():
            if part.name == "chat_id":
                chat_id = (await part.text()).strip()
            elif part.name == "text":
                text = (await part.text()).strip()
            elif part.name == "photo":
                photo_bytes = await part.read()

        if not chat_id:
            return web.json_response({"ok": False, "error": "chat_id required"}, status=400)
        if not photo_bytes:
            return web.json_response({"ok": False, "error": "photo required"}, status=400)
    except Exception as e:
        logger.error("Failed to parse request: %s", e)
        return web.json_response({"ok": False, "error": str(e)}, status=400)

    # 3. Build InternalMessage
    image_base64 = base64.b64encode(photo_bytes).decode("utf-8")
    msg = InternalMessage(
        chat_id=chat_id,
        user_id="api",
        username="Frigate",
        text=text,
        image_base64=image_base64,
    )

    # 4. Process through engine
    try:
        response = await engine.process(msg)
    except Exception as e:
        logger.error("Engine error: %s", e)
        return web.json_response({"ok": False, "error": "engine error"}, status=500)

    # 5. Send response to chat via Telegram Bot
    if response and response.text:
        try:
            await bot.send_message(chat_id, InternalResponse.sanitize(response.text))
        except Exception as e:
            logger.error("Failed to send message: %s", e)
            return web.json_response({"ok": False, "error": "send failed"}, status=502)

    return web.json_response({"ok": True})
