import asyncio
import logging
import sys

from pyrogram import Client, idle

from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    SESSION_STRING,
    BOT_NAME,
)

from database.mongodb import ping_db, close_db
from database.redis_db import connect_redis, close_redis
from handlers import register_handlers
from stream import setup_stream
from clone_manager import clone_manager
from auto_broadcast import auto_broadcast_loop


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

LOGGER = logging.getLogger("v3_musicbot")


# --------------------------------------------------
# BOT CLIENT
# --------------------------------------------------

bot = Client(
    "v3_musicbot_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


assistant = None
music_stream = None


# --------------------------------------------------
# ASSISTANT CLIENT
# --------------------------------------------------

def create_assistant():
    if not SESSION_STRING or SESSION_STRING.startswith("YOUR_"):
        raise RuntimeError(
            "SESSION_STRING is missing. "
            "Add a valid assistant session in your environment."
        )

    return Client(
        "v3_musicbot_assistant",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        no_updates=True,
    )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

async def start_main_bot_with_retry(max_attempts=5):
    """Retry only Telegram's transient internal authorization failures."""
    delays = (5, 10, 20, 30)
    for attempt in range(1, max_attempts + 1):
        try:
            await bot.start()
            return
        except Exception as exc:
            error_text = str(exc).upper()
            transient_telegram_500 = (
                "RPC_CALL_FAIL" in error_text
                or "INTERNAL_SERVER_ERROR_500" in type(exc).__module__.upper()
            )
            if not transient_telegram_500 or attempt >= max_attempts:
                raise

            delay = delays[min(attempt - 1, len(delays) - 1)]
            LOGGER.warning(
                "Telegram returned a temporary 500 during bot authorization "
                "(attempt %s/%s). Retrying in %s seconds.",
                attempt, max_attempts, delay,
            )
            await asyncio.sleep(delay)


async def main():
    global assistant, music_stream

    bot_started = False
    assistant_started = False
    broadcast_task = None

    try:
        # MongoDB
        LOGGER.info("Checking MongoDB connection...")
        await ping_db()
        LOGGER.info("MongoDB connection successful.")

        # Redis
        LOGGER.info("Connecting to Redis...")
        await connect_redis()

        # Start main bot. Telegram may briefly fail auth.ImportBotAuthorization
        # with RPC_CALL_FAIL; retry that server-side error without masking
        # invalid tokens or other permanent configuration failures.
        await start_main_bot_with_retry()
        bot_started = True

        me = await bot.get_me()
        LOGGER.info("Bot started: @%s", me.username or me.id)

        # Start assistant
        assistant = create_assistant()
        await assistant.start()
        assistant_started = True
        LOGGER.info("Assistant account connected.")

        # Start music stream
        music_stream = setup_stream(assistant)
        await music_stream.start()
        LOGGER.info("Music stream initialized.")

        # Register main bot handlers
        register_handlers(
            bot,
            music_stream,
            assistant,
        )
        LOGGER.info("Main bot handlers registered.")

        # Periodic group feature announcements (default: every 24 hours).
        broadcast_task = asyncio.create_task(
            auto_broadcast_loop(bot),
            name="auto-promo-broadcast",
        )
        LOGGER.info("Automatic group promo broadcast scheduled.")

        # Start cloned bots
        LOGGER.info("Initializing Clone Manager...")
        await clone_manager.start_all(
            music_stream,
            assistant,
        )
        LOGGER.info("Clone Manager initialized.")

        LOGGER.info("Student Protection System handlers registered.")
        LOGGER.info("%s bot start ho gya ab govind ko apni setting ki dilwa.", BOT_NAME)

        # Keep all clients running
        await idle()

    except Exception:
        LOGGER.exception("Bot startup/runtime failed.")
        raise

    finally:
        # Stop the promo task cleanly before shutting down the bot client.
        if broadcast_task:
            broadcast_task.cancel()
            try:
                await broadcast_task
            except asyncio.CancelledError:
                pass
            except Exception:
                LOGGER.exception("Auto broadcast shutdown failed.")

        # Stop cloned bots first
        try:
            await clone_manager.stop_all()
        except Exception:
            LOGGER.exception("Clone Manager shutdown failed.")

        # Stop music stream
        if music_stream:
            try:
                await music_stream.shutdown()
            except Exception:
                LOGGER.exception("Music stream shutdown failed.")

        # Stop assistant
        if assistant and assistant_started:
            try:
                await assistant.stop()
            except Exception:
                LOGGER.exception("Assistant shutdown failed.")

        # Stop main bot
        if bot_started:
            try:
                await bot.stop()
            except Exception:
                LOGGER.exception("Bot shutdown failed.")

        # Close Redis
        try:
            await close_redis()
        except Exception:
            LOGGER.exception("Redis shutdown failed.")

        # Close MongoDB
        try:
            await close_db()
        except Exception:
            LOGGER.exception("MongoDB shutdown failed.")

        LOGGER.info("Bot shutdown completed.")


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
