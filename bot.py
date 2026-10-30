
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
from handlers import register_handlers
from stream import setup_stream


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

LOGGER = logging.getLogger("v3_musicbot")

bot = Client(
    "v3_musicbot_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

assistant = None
music_stream = None


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


async def main():
    global assistant, music_stream

    bot_started = False
    assistant_started = False

    try:
        LOGGER.info("Checking MongoDB connection...")
        await ping_db()
        LOGGER.info("MongoDB connection successful.")

        await bot.start()
        bot_started = True

        me = await bot.get_me()
        LOGGER.info("Bot started: @%s", me.username or me.id)

        assistant = create_assistant()
        await assistant.start()
        assistant_started = True

        LOGGER.info("Assistant account connected.")

        music_stream = setup_stream(assistant)
        await music_stream.start()

        register_handlers(bot, music_stream, assistant)

        LOGGER.info("%s is ready.", BOT_NAME)

        await idle()

    except Exception:
        LOGGER.exception("Bot startup/runtime failed.")
        raise

    finally:
        if music_stream:
            try:
                await music_stream.shutdown()
            except Exception:
                LOGGER.exception("Music stream shutdown failed.")

        if assistant and assistant_started:
            try:
                await assistant.stop()
            except Exception:
                LOGGER.exception("Assistant shutdown failed.")

        if bot_started:
            try:
                await bot.stop()
            except Exception:
                LOGGER.exception("Bot shutdown failed.")

        try:
            await close_db()
        except Exception:
            LOGGER.exception("MongoDB shutdown failed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
