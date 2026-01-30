import logging
import json
import os
import random
import asyncio
from datetime import datetime, time
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import RetryAfter, Forbidden, BadRequest, TelegramError
import pytz

# Timezone for scheduling (UTC is recommended by python-telegram-bot docs)
SCHEDULE_TIMEZONE = pytz.UTC
# Daily message time: 20:00 UTC (equivalent to 17:00 America/Buenos_Aires during standard time)
DAILY_TIME = time(hour=20, minute=0, tzinfo=SCHEDULE_TIMEZONE)

# Rate limiting: delay between messages to avoid flood limits (in seconds)
MESSAGE_DELAY = 0.1  # 100ms between messages

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

USERS_FILE = "users.json"


def load_users():
    """Load user IDs from file."""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_users(users):
    """Save user IDs to file."""
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)


# Global set of user IDs
subscribed_users = load_users()

# Song database by category
SONGS = {
    "rock": [
        {"title": "Bohemian Rhapsody", "artist": "Queen", "year": "1975"},
        {"title": "Hotel California", "artist": "Eagles", "year": "1976"},
        {"title": "Stairway to Heaven", "artist": "Led Zeppelin", "year": "1971"},
        {"title": "Sweet Child O' Mine", "artist": "Guns N' Roses", "year": "1987"},
        {"title": "Smells Like Teen Spirit", "artist": "Nirvana", "year": "1991"},
    ],
    "pop": [
        {"title": "Billie Jean", "artist": "Michael Jackson", "year": "1983"},
        {"title": "Like a Prayer", "artist": "Madonna", "year": "1989"},
        {"title": "Rolling in the Deep", "artist": "Adele", "year": "2010"},
        {"title": "Shake It Off", "artist": "Taylor Swift", "year": "2014"},
        {"title": "Uptown Funk", "artist": "Mark Ronson ft. Bruno Mars", "year": "2014"},
    ],
    "jazz": [
        {"title": "Take Five", "artist": "Dave Brubeck", "year": "1959"},
        {"title": "So What", "artist": "Miles Davis", "year": "1959"},
        {"title": "Feeling Good", "artist": "Nina Simone", "year": "1965"},
        {"title": "Fly Me to the Moon", "artist": "Frank Sinatra", "year": "1964"},
        {"title": "Autumn Leaves", "artist": "Bill Evans", "year": "1959"},
    ],
    "electronic": [
        {"title": "One More Time", "artist": "Daft Punk", "year": "2001"},
        {"title": "Levels", "artist": "Avicii", "year": "2011"},
        {"title": "Sandstorm", "artist": "Darude", "year": "1999"},
        {"title": "Strobe", "artist": "deadmau5", "year": "2009"},
        {"title": "Midnight City", "artist": "M83", "year": "2011"},
    ],
    "classical": [
        {"title": "Four Seasons - Spring", "artist": "Vivaldi", "year": "1725"},
        {"title": "Symphony No. 5", "artist": "Beethoven", "year": "1808"},
        {"title": "Clair de Lune", "artist": "Debussy", "year": "1905"},
        {"title": "Canon in D", "artist": "Pachelbel", "year": "1700"},
        {"title": "The Four Seasons - Winter", "artist": "Vivaldi", "year": "1725"},
    ],
}


def format_song(song, category):
    """Format song info for display."""
    return f"🎵 *{song['title']}*\n👤 {song['artist']}\n📅 {song['year']}\n🏷️ {category.capitalize()}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - subscribe user to daily songs."""
    user_id = update.effective_user.id
    subscribed_users.add(user_id)
    save_users(subscribed_users)
    
    help_text = (
        "Привет! 🎵\n\n"
        "Я бот с подборкой песен!\n"
        "Каждый день в 20:00 UTC (17:00 по Буэнос-Айресу) я присылаю случайную песню.\n\n"
        "Доступные команды:\n"
        "/rock - рок песни\n"
        "/pop - поп музыка\n"
        "/jazz - джаз\n"
        "/electronic - электронная музыка\n"
        "/classical - классическая музыка\n"
        "/random - случайная песня\n"
        "/stop - отписаться от ежедневных песен"
    )
    
    await update.message.reply_text(help_text)
    logger.info(f"User {user_id} subscribed")


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stop command - unsubscribe user."""
    user_id = update.effective_user.id
    subscribed_users.discard(user_id)
    save_users(subscribed_users)
    
    await update.message.reply_text(
        "Ты отписался от ежедневных песен.\n"
        "Если захочешь вернуться - просто нажми /start"
    )
    logger.info(f"User {user_id} unsubscribed")


async def send_random_song(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a random song from any category."""
    all_songs = []
    for category, songs in SONGS.items():
        for song in songs:
            all_songs.append((song, category))
    
    song, category = random.choice(all_songs)
    await update.message.reply_text(format_song(song, category), parse_mode="Markdown")


async def send_category_song(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str) -> None:
    """Send a random song from specific category."""
    if category in SONGS:
        song = random.choice(SONGS[category])
        await update.message.reply_text(format_song(song, category), parse_mode="Markdown")
    else:
        await update.message.reply_text("Такой категории нет!")


# Category command handlers
async def rock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_category_song(update, context, "rock")

async def pop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_category_song(update, context, "pop")

async def jazz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_category_song(update, context, "jazz")

async def electronic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_category_song(update, context, "electronic")

async def classical(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_category_song(update, context, "classical")


async def send_daily_song(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send random song to all subscribed users daily with proper error handling."""
    all_songs = []
    for category, songs in SONGS.items():
        for song in songs:
            all_songs.append((song, category))
    
    song, category = random.choice(all_songs)
    message = "🎵 Песня дня!\n\n" + format_song(song, category)
    
    # Track users to remove (blocked bot, etc.)
    users_to_remove = set()
    successful_sends = 0
    failed_sends = 0
    
    for user_id in list(subscribed_users):
        try:
            await context.bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")
            logger.info(f"Daily song sent to user {user_id}")
            successful_sends += 1
            
            # Small delay to avoid flood limits
            await asyncio.sleep(MESSAGE_DELAY)
            
        except RetryAfter as e:
            # Rate limit hit - wait and retry once
            retry_after = e.retry_after
            logger.warning(f"Rate limit hit for user {user_id}, waiting {retry_after}s")
            await asyncio.sleep(retry_after)
            try:
                await context.bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")
                successful_sends += 1
            except Exception as retry_error:
                logger.error(f"Failed to send to {user_id} after retry: {retry_error}")
                failed_sends += 1
                
        except Forbidden:
            # User blocked the bot
            logger.warning(f"User {user_id} blocked the bot, removing from subscribers")
            users_to_remove.add(user_id)
            failed_sends += 1
            
        except BadRequest as e:
            # Check if it's a "chat not found" error
            if "chat not found" in str(e).lower():
                logger.warning(f"Chat {user_id} not found, removing from subscribers")
                users_to_remove.add(user_id)
            else:
                # Other bad request errors (malformed message, etc.)
                logger.error(f"BadRequest for user {user_id}: {e}")
            failed_sends += 1
            
        except TelegramError as e:
            logger.error(f"Telegram error sending to {user_id}: {e}")
            failed_sends += 1
            
        except Exception as e:
            logger.error(f"Unexpected error sending to {user_id}: {e}")
            failed_sends += 1
    
    # Remove users who blocked the bot or have invalid chats
    if users_to_remove:
        subscribed_users.difference_update(users_to_remove)
        save_users(subscribed_users)
        logger.info(f"Removed {len(users_to_remove)} inactive users from subscribers")
    
    logger.info(f"Daily song delivery complete: {successful_sends} successful, {failed_sends} failed")


async def test_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send test daily song immediately."""
    await update.message.reply_text("Отправляю тестовую песню дня...")
    await send_daily_song(context)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error("Exception while handling an update:", exc_info=context.error)


async def post_init(application: Application) -> None:
    """Set up bot commands menu after initialization."""
    commands = [
        BotCommand("start", "Подписаться на ежедневные песни"),
        BotCommand("rock", "Рок песни"),
        BotCommand("pop", "Поп музыка"),
        BotCommand("jazz", "Джаз"),
        BotCommand("electronic", "Электронная музыка"),
        BotCommand("classical", "Классическая музыка"),
        BotCommand("random", "Случайная песня"),
        BotCommand("stop", "Отписаться от ежедневных песен"),
        BotCommand("test", "Отправить тестовую песню"),
    ]
    await application.bot.set_my_commands(commands)


def main() -> None:
    """Start the bot."""
    # Try to load token from .env file first
    token = None
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("BOT_TOKEN="):
                    token = line.strip().split("=", 1)[1].strip().strip('"\'')
                    break
    
    # Fallback to environment variable
    if not token:
        token = os.getenv("BOT_TOKEN")
    
    if not token:
        logger.error("BOT_TOKEN not found in .env file or environment variables!")
        return

    application = Application.builder().token(token).post_init(post_init).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("random", send_random_song))
    application.add_handler(CommandHandler("rock", rock))
    application.add_handler(CommandHandler("pop", pop))
    application.add_handler(CommandHandler("jazz", jazz))
    application.add_handler(CommandHandler("electronic", electronic))
    application.add_handler(CommandHandler("classical", classical))
    application.add_handler(CommandHandler("test", test_daily))

    # Register error handler
    application.add_error_handler(error_handler)

    # Schedule daily song at 20:00 UTC
    job_queue = application.job_queue
    job_queue.run_daily(
        send_daily_song,
        time=DAILY_TIME,
        name="daily_song",
        job_kwargs={'misfire_grace_time': 3600}  # Allow 1 hour grace period if bot was down
    )

    logger.info(f"Bot started - daily messages scheduled for {DAILY_TIME}")
    application.run_polling()


if __name__ == "__main__":
    main()
