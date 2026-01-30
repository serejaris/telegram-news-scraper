# Telegram Music Bot

Телеграм-бот с подборкой песен и AI-чатом.

## Возможности

- Песни по жанрам (rock, pop, jazz, electronic, classical)
- Ежедневная рассылка "Песня дня" в 20:00 UTC
- AI-чат через OpenRouter (любая модель: DeepSeek, Claude, GPT, Gemini)

## Архитектура

```mermaid
flowchart TB
    subgraph Telegram
        User([User])
    end

    subgraph Bot["bot.py"]
        CMD[Command Handlers]
        MSG[Message Handler]
        SCHED[Job Queue]
    end

    subgraph External
        TG_API[Telegram API]
        OR_API[OpenRouter API]
    end

    subgraph Storage
        USERS[(users.json)]
    end

    User -->|/start, /rock, etc| TG_API
    User -->|text message| TG_API
    TG_API --> CMD
    TG_API --> MSG

    CMD -->|subscribe/unsubscribe| USERS
    CMD -->|song response| TG_API

    MSG -->|"🤔 Думаю..."| TG_API
    MSG -->|chat request| OR_API
    OR_API -->|AI response| MSG
    MSG -->|edit message| TG_API

    SCHED -->|daily 20:00 UTC| USERS
    SCHED -->|broadcast song| TG_API

    TG_API --> User
```

## AI Chat Flow

```mermaid
sequenceDiagram
    participant U as User
    participant B as Bot
    participant T as Telegram
    participant O as OpenRouter

    U->>T: Привет!
    T->>B: Update (text)
    B->>T: send "🤔 Думаю..."
    B->>T: send_chat_action(typing)
    T->>U: typing indicator
    B->>O: chat.completions.create()
    O-->>B: AI response
    B->>T: edit_message(response)
    T->>U: AI ответ в стихах
```

## Команды

| Команда | Описание |
|---------|----------|
| `/start` | Подписка на ежедневные песни |
| `/stop` | Отписка |
| `/rock` | Рок-песня |
| `/pop` | Поп-музыка |
| `/jazz` | Джаз |
| `/electronic` | Электроника |
| `/classical` | Классика |
| `/random` | Случайная песня |
| `/test` | Тестовая рассылка |

Любое текстовое сообщение (не команда) — отправляется AI.

## Установка

```bash
# 1. Клонировать
git clone https://github.com/serejaris/telegram-news-scraper.git
cd telegram-news-scraper

# 2. Виртуальное окружение
python -m venv .venv
source .venv/bin/activate

# 3. Зависимости
pip install -r requirements.txt

# 4. Конфигурация
cp .env.example .env
# Заполнить BOT_TOKEN и OPENROUTER_API_KEY

# 5. Запуск
python bot.py
```

## Конфигурация (.env)

```bash
BOT_TOKEN=...                              # Telegram bot token
OPENROUTER_API_KEY=...                     # OpenRouter API key
AI_MODEL=deepseek/deepseek-r1-0528:free    # Модель (опционально)
AI_SYSTEM_PROMPT=Ты помощник...            # Системный промпт (опционально)
```

Доступные модели: `google/gemini-2.0-flash-exp:free`, `deepseek/deepseek-chat`, `anthropic/claude-3.5-sonnet`, `meta-llama/llama-3.3-70b-instruct:free`

## Деплой

Бот должен работать постоянно для ежедневных рассылок:
- [Railway](https://railway.app)
- [Heroku](https://heroku.com)
- VPS
