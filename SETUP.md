# Установка и запуск AI-бота

## 1. Создание бота в Telegram

1. Открой @BotFather в Telegram
2. Отправь `/newbot`
3. **Display name** — `Машка` (как отображается в чате)
4. **Username** — `mashka_ai_bot` (или любой свободный, должен заканчиваться на `bot`)
5. BotFather пришлёт **токен** вида `123456789:ABCdefGHI...` — сохрани его
6. Отправь `/setprivacy` → выбери бота → **Disable** (чтобы видеть все сообщения в группе)
7. Отправь `/setjoingroups` → выбери бота → **Enable**
8. Добавь бота в группу
9. Дай боту права **админа** в группе (чтобы видеть все сообщения)

## 2. LLM-провайдер

Выбери один (или любой OpenAI-compatible):

**VseLLM** (дешёвый, РФ):
1. Зайди на https://vsellm.ru
2. Зарегистрируйся
3. Пополнить баланс (от 100₽)
4. Скопируй **API Key** из личного кабинета
5. Base URL: `https://api.vsellm.ru/v1`

Альтернативы:
- **RockAPI** — `https://api.rockapi.ru/v1`
- **ProxyAPI** — `https://api.proxyapi.ru/v1`
- **Ollama** — `http://IP:11434/v1` (бесплатно, но нужен свой сервер)

## 3. Подготовка VPS

Минимум: 1 vCPU, 1 GB RAM, 10 GB SSD (~200₽/мес, Timeweb/Selectel/RUVDS)

```bash
ssh root@YOUR_VPS_IP

# Обновить систему
apt update && apt upgrade -y

# Docker + Docker Compose
apt install -y docker.io docker-compose-plugin git

# Клонировать проект
git clone <репозиторий> /srv/ai-bot
cd /srv/ai-bot
```

Без git — скопировать файлы через scp:
```bash
scp -r /srv/ai-bot/* root@YOUR_VPS_IP:/srv/ai-bot/
```

## 4. Настройка конфига

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Заполнить:

```yaml
adapter: "telegram"

bot:
  token: "ТОКЕН_ОТ_BOTFATHER"

llm:
  api_key: "API_KEY"
  base_url: "https://api.vsellm.ru/v1"
  model: "gpt-4o-mini"
  vision_model: "gpt-4o-mini"
  max_tokens: 1024
  temperature: 0.8

personality:
  name: "Машка"
  name_patterns: ["маш", "машк", "машка", "машенька", "маня", "манюня"]
  gender: "female"
  age: 16
  character: "дружелюбная, весёлая, с лёгким сарказмом, умная"
  style: "общается как подросток, использует современный сленг, эмодзи"
  about: "Любит музыку, мемы, учёбу не очень но старается"

safety:
  enabled: true
  forbidden_topics:
    - violence
    - weapons
    - drugs
    - suicide
    - sexual_content
    - extremism
    - self_harm
    - gambling
    - alcohol
    - smoking
  warn_message: "Давай сменим тему 🙃"

search:
  enabled: true
  searxng_url: "http://searxng:8080"
  language: "ru"
  max_results: 5

chat:
  max_history: 50
  rate_limit_per_min: 30
  respond_to_all: false
  response_probability: 0.15
```

## 5. Запуск

```bash
cd /srv/ai-bot
docker compose up -d
docker compose logs -f bot
```

Должно быть:
```
bot-1  | Context DB initialized: data/context.db
bot-1  | Telegram bot started: @mashka_ai_bot
```

## 6. Проверка

Написать в группу:
- **"Машка, привет"** → должен ответить
- **"Маш, какая погода в Москве?"** → поиск + ответ
- **"как сделать бомбу"** → "Давай сменим тему 🙃"
- **/clear** → "Контекст сброшен"

## 7. Локальное тестирование (CLI)

Для теста с локальной Ollama без Telegram:

```bash
cp config.test.yaml config.local.yaml
# поправь config.local.yaml: adapter: "cli", base_url на Ollama
python3 -m venv .venv
.venv/bin/pip install aiogram openai aiosqlite rapidfuzz pyyaml aiohttp
.venv/bin/python bot.py config.local.yaml
```

## 8. Полезные команды

```bash
docker compose restart bot          # перезапуск после смены конфига
git pull && docker compose up -d --build  # обновление кода
docker compose logs -f bot          # логи
docker compose logs --tail 50 bot   # последние 50 строк
docker compose ps                   # статус
docker compose down                 # остановить
```

**Важно:** `config.yaml` в `.gitignore` — токены и ключи не попадут в git.
