
import logging

from pyrogram import filters
from pyrogram.types import CallbackQuery
from pyrogram.errors import MessageNotModified

from config import (
    START_IMAGE,
    SUPPORT_CHANNEL,
    SUPPORT_CHAT,
    OWNER_ID,
    BOT_NAME,
)
from buttons import start_buttons, help_buttons
from database.mongodb import add_user


LOGGER = logging.getLogger(__name__)


START_TEXT = (
    f"🎧 **Welcome to {BOT_NAME}!**\n\n"
    "I can play music in your group's voice chat.\n\n"
    "Use `/play song name` to search and play music.\n"
    "Use `/vplay song name` to play video in voice chat.\n"
    "Use `/queue` to see upcoming tracks and `/help` for commands."
)

HELP_TEXT = (
    "**🎧 Music Bot Help**\n\n"
    "`/play <song or YouTube link>` — search/play audio\n"
    "`/vplay <song or YouTube link>` — video stream\n"
    "`/queue` — show upcoming tracks\n"
    "`/now` — show current track\n"
    "`/pause`, `/resume`, `/skip`, `/stop` — playback controls\n"
    "`/clearqueue` — clear queue"
)


def register_start_handlers(app):

    @app.on_message(filters.command("start") & filters.private)
    async def start_command(client, message):
        if message.from_user:
            try:
                await add_user(message.from_user.id)
            except Exception:
                LOGGER.exception("Failed to save user")

        try:
            me = await client.get_me()

            markup = start_buttons(
                OWNER_ID,
                SUPPORT_CHAT,
                SUPPORT_CHANNEL,
                me.username or "",
            )

            if START_IMAGE:
                try:
                    await message.reply_photo(
                        photo=START_IMAGE,
                        caption=START_TEXT,
                        reply_markup=markup,
                    )
                    return
                except Exception:
                    LOGGER.warning(
                        "Start image failed; falling back to text",
                        exc_info=True,
                    )

            await message.reply_text(
                START_TEXT,
                reply_markup=markup,
                disable_web_page_preview=True,
            )

        except Exception:
            LOGGER.exception("Start command failed")
            await message.reply_text(
                "Sorry, the start menu could not be loaded. "
                "Please try again later."
            )

    @app.on_message(filters.command("help"))
    async def help_command(client, message):
        try:
            await message.reply_text(
                HELP_TEXT,
                reply_markup=help_buttons(),
            )
        except Exception:
            LOGGER.exception("Help command failed")
            await message.reply_text(HELP_TEXT)

    @app.on_callback_query(filters.regex("^help_cmd$"))
    async def help_callback(client, query: CallbackQuery):
        await query.answer()

        try:
            await query.message.edit_text(
                HELP_TEXT,
                reply_markup=help_buttons(),
            )
        except MessageNotModified:
            pass
        except Exception:
            LOGGER.exception("Help menu callback failed")

    @app.on_callback_query(filters.regex("^start_home$"))
    async def home_callback(client, query: CallbackQuery):
        await query.answer()

        try:
            me = await client.get_me()

            markup = start_buttons(
                OWNER_ID,
                SUPPORT_CHAT,
                SUPPORT_CHANNEL,
                me.username or "",
            )

            await query.message.edit_text(
                START_TEXT,
                reply_markup=markup,
                disable_web_page_preview=True,
            )

        except MessageNotModified:
            pass
        except Exception:
            LOGGER.exception("Home menu callback failed")
            try:
                await query.message.reply_text(START_TEXT)
            except Exception:
                LOGGER.exception("Home menu fallback failed")
