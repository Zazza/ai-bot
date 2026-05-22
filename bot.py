"""AI Bot — entry point."""

from __future__ import annotations

import asyncio
import logging
import sys

from config import load_config
from core.engine import Engine
from llm.client import LLMClient
from services.context import ContextService
from services.name_match import NameMatcher
from services.safety import SafetyFilter
from services.search import SearchService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("bot")


async def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = load_config(config_path)

    # Engine
    engine = Engine(config)

    # LLM
    llm = LLMClient(config.llm)

    # Context (SQLite)
    context = ContextService()
    await context.init()

    # Safety
    safety = SafetyFilter(config, llm_client=llm) if config.safety.enabled else None

    # Search (optional component)
    search = None
    if config.search.enabled:
        search = SearchService(config)
        await search.init()

    # Name matcher
    name_matcher = NameMatcher(config.personality.name_patterns) if config.personality.name_patterns else None

    # Wire everything
    engine.set_services(
        llm=llm,
        context=context,
        safety=safety,
        search=search,
        name_matcher=name_matcher,
    )

    # Adapter
    adapter = _create_adapter(config, engine)
    if adapter is None:
        logger.error("Unknown adapter: %s", config.adapter)
        sys.exit(1)

    logger.info("Starting with adapter: %s", config.adapter)

    try:
        await adapter.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await adapter.stop()
        await context.close()
        if search:
            await search.close()


def _create_adapter(config, engine):
    """Фабрика адаптеров."""
    if config.adapter == "telegram":
        from adapters.telegram.adapter import TelegramAdapter
        return TelegramAdapter(engine, config)
    if config.adapter == "cli":
        from adapters.cli.adapter import CLIAdapter
        return CLIAdapter(engine, config)
    # TODO: websocket adapter
    return None


if __name__ == "__main__":
    asyncio.run(main())
