import logging
import os
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import AsyncOpenAI

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# AI Configuration (loaded in main())
ai_client = None
AI_MODEL = "google/gemini-2.0-flash-exp:free"
AI_SYSTEM_PROMPT = "Ты Гарри Поттер, который общается в стихотворной форме."


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
        response = await ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ]
        )
        ai_response = response.choices[0].message.content
        await thinking_msg.edit_text(ai_response)
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
    global ai_client, AI_MODEL, AI_SYSTEM_PROMPT

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
