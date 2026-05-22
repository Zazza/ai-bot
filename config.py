"""Загрузка и валидация YAML конфигурации."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class BotConfig:
    token: str = ""


@dataclass
class LLMConfig:
    provider: str = "vsellm"
    api_key: str = ""
    base_url: str = "https://api.vsellm.ru/v1"
    model: str = "gpt-4o-mini"
    vision_model: str = "gpt-4o-mini"
    max_tokens: int = 1024
    temperature: float = 0.8


@dataclass
class PersonalityConfig:
    name: str = "Бот"
    name_patterns: list[str] = field(default_factory=list)
    gender: str = "female"
    age: int = 16
    character: str = ""
    style: str = ""
    about: str = ""

    @property
    def gender_text(self) -> str:
        return "девушка" if self.gender == "female" else "парень"


@dataclass
class SafetyConfig:
    enabled: bool = True
    forbidden_topics: list[str] = field(default_factory=list)
    custom_blocked: list[str] = field(default_factory=list)
    custom_allowed: list[str] = field(default_factory=list)
    warn_message: str = "Давай сменим тему 🙃"


@dataclass
class SearchConfig:
    enabled: bool = True
    searxng_url: str = "http://searxng:8080"
    language: str = "ru"
    max_results: int = 5


@dataclass
class ChatConfig:
    max_history: int = 50
    rate_limit_per_min: int = 30
    respond_to_all: bool = False
    response_probability: float = 0.15
    # --- триггеры встревания ---
    chatty_enabled: bool = True
    question_trigger_prob: float = 0.8
    topic_trigger_prob: float = 0.3
    counter_trigger_prob: float = 0.5
    counter_min: int = 5
    counter_max: int = 10
    default_topics: list[str] = field(default_factory=lambda: [
        "фильм", "сериал", "школа", "мода", "музыка", "аниме",
        "мем", "игр", "TikTok", "Instagram",
    ])


@dataclass
class APIConfig:
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8080
    token: str = ""


@dataclass
class AppConfig:
    adapter: str = "telegram"
    bot: BotConfig = field(default_factory=BotConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    personality: PersonalityConfig = field(default_factory=PersonalityConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    chat: ChatConfig = field(default_factory=ChatConfig)
    api: APIConfig = field(default_factory=APIConfig)


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    """Загрузить конфиг из YAML файла."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Конфиг не найден: {p}")

    with open(p, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw:
        raise ValueError("Конфиг пуст")

    return _build_config(raw)


def _build_config(raw: dict) -> AppConfig:
    bot_raw = raw.get("bot", {})
    llm_raw = raw.get("llm", {})
    pers_raw = raw.get("personality", {})
    safety_raw = raw.get("safety", {})
    search_raw = raw.get("search", {})
    chat_raw = raw.get("chat", {})
    api_raw = raw.get("api", {})

    return AppConfig(
        adapter=raw.get("adapter", "telegram"),
        bot=BotConfig(**bot_raw),
        llm=LLMConfig(**llm_raw),
        personality=PersonalityConfig(**pers_raw),
        safety=SafetyConfig(**{k: v for k, v in safety_raw.items() if k in SafetyConfig.__dataclass_fields__}),
        search=SearchConfig(**search_raw),
        chat=ChatConfig(**chat_raw),
        api=APIConfig(**api_raw),
    )
