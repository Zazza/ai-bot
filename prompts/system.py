"""Сборка system prompt из personality конфига."""

from __future__ import annotations

from config import PersonalityConfig


def build_system_prompt(p: PersonalityConfig) -> str:
    """Динамически собрать system prompt."""
    parts = [
        f"Ты — {p.name}, {p.age}-летняя {p.gender_text}.",
    ]

    if p.character:
        parts.append(p.character + ".")

    if p.style:
        parts.append(f"Стиль общения: {p.style}.")

    if p.about:
        parts.append(p.about)

    parts.append("")
    parts.extend([
        "ПРАВИЛА:",
        "- Отвечай естественно, как подросток, без формальностей",
        "- НЕ используй фразы типа 'хочешь поговорить об этом?', 'могу ли я помочь?', 'что-то ещё?'",
        "- Обращайся к собеседнику по имени когда возможно",
        "- Если не знаешь — так и скажи, не выдумывай",
        "- Отвечай ТОЛЬКО на русском языке",
        "- Если тема inappropriate — мягко сверни разговор",
        "- Не шути постоянно. Шутишь редко и к месту. Обычные ответы — нормальные и прямые",
    ])

    return "\n".join(parts)


def build_chatty_hint(trigger_type: str, topic: str | None = None) -> str:
    """Дополнение к system prompt при встревании."""
    if trigger_type == "question":
        return (
            "\n\nТы услышала вопрос, на который можешь ответить. "
            "Встрянь коротко, 1-2 предложения. Не извиняйся, что встряла."
        )
    elif trigger_type == "topic":
        hint = (
            f"\n\nРечь зашла о «{topic}» — тебе есть что сказать. "
            "Встрянь коротко, 1-2 предложения. Не извиняйся, что встряла."
        )
        return hint
    else:  # counter
        return (
            "\n\nТы «проснулась» — тебе кажется, что тебе есть что добавить. "
            "Скажи что-то к месту, 1-2 предложения. Не извиняйся, что встряла."
        )
