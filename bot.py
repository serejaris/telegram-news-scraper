import asyncio
import logging
import os
import re
from telegram import Update, BotCommand
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import AsyncOpenAI
from exa_py import Exa

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# AI Configuration (loaded in main())
ai_client = None
exa_client = None
AI_MODEL = "google/gemini-2.0-flash-exp:free"
AI_SYSTEM_PROMPT = "Ты Гарри Поттер, который общается в стихотворной форме."
MAX_MESSAGE_LENGTH = 4096


def markdown_to_html(text: str) -> str:
    """Convert markdown to Telegram HTML format."""
    # Extract and preserve markdown links BEFORE escaping HTML
    links = []

    def preserve_link(match):
        link_text = match.group(1)
        link_url = match.group(2)
        placeholder = f"__LINK_{len(links)}__"
        links.append((link_text, link_url))
        return placeholder

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', preserve_link, text)

    # Escape HTML entities
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Restore links as HTML <a> tags
    for i, (link_text, link_url) in enumerate(links):
        escaped_text = link_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"__LINK_{i}__", f'<a href="{link_url}">{escaped_text}</a>')

    # Headers: ### -> <b>
    text = re.sub(r'^###\s*(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^##\s*(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^#\s*(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    # Bold: **text** -> <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # Italic: *text* -> <i>text</i>
    text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)

    # Code blocks: ```code``` -> <pre>code</pre>
    text = re.sub(r'```[\w]*\n?(.*?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)

    # Inline code: `code` -> <code>code</code>
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    return text


def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split long message into chunks respecting paragraph boundaries."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Find split point: prefer double newline, then single newline, then space
        split_at = text.rfind('\n\n', 0, max_length)
        if split_at == -1:
            split_at = text.rfind('\n', 0, max_length)
        if split_at == -1:
            split_at = text.rfind(' ', 0, max_length)
        if split_at == -1:
            split_at = max_length

        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()

    return chunks


SKIP_SEARCH_WORDS = {"привет", "здравствуй", "хай", "hi", "hello", "спасибо", "благодарю",
                     "ок", "ok", "да", "нет", "пока", "bye", "хорошо", "понял", "ясно"}


def should_search(text: str) -> bool:
    """Determine if we should search for sources."""
    if not exa_client:
        return False
    if len(text) < 15:
        return False
    if text.lower().strip().rstrip("!?.") in SKIP_SEARCH_WORDS:
        return False
    return True


async def search_sources(query: str, num_results: int = 3) -> list[dict]:
    """Search for sources using Exa AI."""
    try:
        result = await asyncio.to_thread(
            exa_client.search_and_contents,
            query,
            type="auto",
            use_autoprompt=True,
            num_results=num_results,
            highlights=True
        )
        sources = []
        for r in result.results:
            sources.append({
                "title": r.title or "Без названия",
                "url": r.url,
                "highlight": r.highlights[0] if r.highlights else "",
                "date": getattr(r, "published_date", None)
            })
        return sources
    except Exception as e:
        logger.warning(f"Exa search failed: {e}")
        return []


def build_prompt_with_sources(query: str, sources: list[dict]) -> str:
    """Build system prompt with source context."""
    if not sources:
        return AI_SYSTEM_PROMPT

    sources_text = "\n".join([
        f"- [{s['title']}]({s['url']}): {s['highlight']}"
        for s in sources
    ])
    return f"""{AI_SYSTEM_PROMPT}

У тебя есть доступ к следующим источникам по теме запроса:
{sources_text}

Используй эти источники в ответе, если они релевантны. В конце ответа добавь раздел "Источники:" со ссылками в формате markdown [название](url). Если источники нерелевантны — не упоминай их."""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    help_text = (
        "Привет! Я AI-бот.\n\n"
        "Просто напиши мне сообщение, и я отвечу."
    )
    await update.message.reply_text(help_text)
    logger.info(f"User {update.effective_user.id} started bot")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages with AI response."""
    if not ai_client:
        await update.message.reply_text("AI не настроен. Добавь OPENROUTER_API_KEY в .env")
        return

    user_text = update.message.text
    chat_id = update.effective_chat.id

    # Send "thinking" placeholder and typing indicator
    thinking_msg = await update.message.reply_text("🤔 Думаю...")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Search for sources if needed
        sources = []
        if should_search(user_text):
            await thinking_msg.edit_text("🔍 Ищу источники...")
            sources = await search_sources(user_text)
            await thinking_msg.edit_text("🤔 Анализирую...")

        system_prompt = build_prompt_with_sources(user_text, sources)

        response = await ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ]
        )
        ai_response = response.choices[0].message.content
        html_response = markdown_to_html(ai_response)
        chunks = split_message(html_response)

        # Edit first message with first chunk
        await thinking_msg.edit_text(chunks[0], parse_mode=ParseMode.HTML)

        # Send remaining chunks as new messages
        for chunk in chunks[1:]:
            await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"AI error: {e}")
        await thinking_msg.edit_text("❌ Не удалось получить ответ")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error("Exception while handling an update:", exc_info=context.error)


async def post_init(application: Application) -> None:
    """Set up bot commands menu after initialization."""
    commands = [
        BotCommand("start", "Начать"),
    ]
    await application.bot.set_my_commands(commands)


def main() -> None:
    """Start the bot."""
    global ai_client, exa_client, AI_MODEL, AI_SYSTEM_PROMPT

    # Load config from .env file
    env_vars = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip().strip('"\'')

    token = env_vars.get("BOT_TOKEN") or os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN not found in .env file or environment variables!")
        return

    # Initialize AI client if API key is available
    openrouter_key = env_vars.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        ai_client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
        )
        AI_MODEL = env_vars.get("AI_MODEL") or os.getenv("AI_MODEL") or AI_MODEL
        AI_SYSTEM_PROMPT = env_vars.get("AI_SYSTEM_PROMPT") or os.getenv("AI_SYSTEM_PROMPT") or AI_SYSTEM_PROMPT
        logger.info(f"AI enabled with model: {AI_MODEL}")
    else:
        logger.warning("OPENROUTER_API_KEY not set - AI chat disabled")

    # Initialize Exa client for source search
    exa_key = env_vars.get("EXA_API_KEY") or os.getenv("EXA_API_KEY")
    if exa_key:
        exa_client = Exa(api_key=exa_key)
        logger.info("Exa search enabled")
    else:
        logger.warning("EXA_API_KEY not set - source search disabled")

    application = Application.builder().token(token).post_init(post_init).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))

    # AI message handler (responds to any text that's not a command)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Register error handler
    application.add_error_handler(error_handler)

    logger.info("Bot started")
    application.run_polling()


if __name__ == "__main__":
    main()
