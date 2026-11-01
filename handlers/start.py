
import logging
import html

from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified

from config import (
    START_IMAGE,
    SUPPORT_CHAT,
    SUPPORT_CHANNEL,
    OWNER_ID,
    BOT_NAME,
    LOGGER_ID,
)

from buttons import start_buttons, help_buttons
from database.mongodb import add_user, add_chat
from youtube import get_video_info


LOGGER = logging.getLogger(__name__)


START_TEXT = (
    f"🎧 <b>WELCOME TO {html.escape(BOT_NAME)}!</b>\n\n"
    "✨ Your Ultimate Telegram Music Bot\n\n"
    "🎵 Play your favourite songs directly in "
    "Telegram Voice Chats.\n\n"
    "🎧 High Quality Audio Streaming\n"
    "🎬 Video Streaming Support\n"
    "⏭ Smart Queue & Skip System\n"
    "🎨 Automatic Music Thumbnails\n\n"
    "💫 Add me to your group and enjoy music!"
)


HELP_TEXT = (
    "🎧 <b>GOVIND MUSIC HELP MENU</b>\n\n"
    "<b>🎵 MUSIC COMMANDS</b>\n"
    "• <code>/play song name</code> - Play audio\n"
    "• <code>/vplay song name</code> - Play video\n"
    "• <code>/skip</code> - Skip current song\n"
    "• <code>/pause</code> - Pause playback\n"
    "• <code>/resume</code> - Resume playback\n"
    "• <code>/stop</code> - Stop playback\n"
    "• <code>/queue</code> - Show music queue\n"
    "• <code>/now</code> - Current playing song\n\n"

    "<b>🎛 OTHER COMMANDS</b>\n"
    "• <code>/start</code> - Start the bot\n"
    "• <code>/help</code> - Help menu\n\n"

    "💖 Powered by GOVIND MUSIC"
)


def get_start_keyboard(bot_username):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ ADD ME TO GROUP",
                url=(
                    f"https://t.me/{bot_username}"
                    "?startgroup=true"
                ),
            )
        ],
        [
            InlineKeyboardButton(
                "💬 SUPPORT",
                url=SUPPORT_CHAT,
            ),
            InlineKeyboardButton(
                "📢 UPDATES",
                url=SUPPORT_CHANNEL,
            ),
        ],
        [
            InlineKeyboardButton(
                "🎧 HELP",
                callback_data="help_cmd",
            ),
            InlineKeyboardButton(
                "👑 OWNER",
                user_id=OWNER_ID,
            ),
        ],
    ])


def get_help_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🏠 HOME",
                callback_data="start_home",
            ),
            InlineKeyboardButton(
                "✖ CLOSE",
                callback_data="ctrl_close",
            ),
        ]
    ])


async def send_start(client, message):

    me = await client.get_me()

    if message.from_user:
        try:
            await add_user(message.from_user.id)
        except Exception:
            LOGGER.exception("Could not save user.")

    keyboard = get_start_keyboard(me.username or "")

    if START_IMAGE:

        try:
            await message.reply_photo(
                photo=START_IMAGE,
                caption=START_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
            return

        except Exception:
            LOGGER.exception("Start image failed.")

    await message.reply_text(
        START_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


async def send_help(message):

    await message.reply_text(
        HELP_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=get_help_keyboard(),
    )


async def send_video_info(client, message, video_id):

    status = await message.reply_text(
        "🔎 <b>Fetching YouTube information...</b>",
        parse_mode=ParseMode.HTML,
    )

    try:

        info = await get_video_info(
            f"https://www.youtube.com/watch?v={video_id}"
        )

        title = html.escape(info.get("title", "Unknown"))
        channel = html.escape(info.get("channel", "Unknown"))
        duration = html.escape(
            str(info.get("duration_text", "Unknown"))
        )

        views = info.get("views", 0)
        url = info.get("webpage_url")

        caption = (
            "🎵 <b>TRACK INFORMATION</b>\n\n"
            f"📌 <b>Title:</b> {title}\n"
            f"⏳ <b>Duration:</b> {duration}\n"
            f"👀 <b>Views:</b> {views:,}\n"
            f"🎤 <b>Channel:</b> {channel}\n\n"
            f"🔗 <a href=\"{html.escape(url, quote=True)}\">"
            "Watch on YouTube</a>\n\n"
            f"💖 <b>{html.escape(BOT_NAME)}</b>"
        )

        thumbnail = info.get("thumbnail")

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "▶ WATCH ON YOUTUBE",
                    url=url,
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 HOME",
                    callback_data="start_home",
                )
            ],
        ])

        await status.delete()

        if thumbnail:

            await client.send_photo(
                chat_id=message.chat.id,
                photo=thumbnail,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )

        else:

            await message.reply_text(
                caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )

    except Exception:

        LOGGER.exception("Video information failed.")

        await status.edit_text(
            "❌ Could not retrieve YouTube information."
        )


def register_start_handlers(app):

    @app.on_message(
        filters.command("start") & filters.private
    )
    async def start_command(client, message):

        try:

            args = message.text.split(maxsplit=1)

            if len(args) > 1:

                payload = args[1].strip()

                if payload == "help":
                    return await send_help(message)

                if payload.startswith("info_"):

                    video_id = payload[5:]

                    if video_id:
                        return await send_video_info(
                            client,
                            message,
                            video_id,
                        )

                if payload == "verify":

                    return await message.reply_text(
                        "✅ Verification successful!"
                    )

            await send_start(client, message)

            if LOGGER_ID:

                try:
                    await client.send_message(
                        LOGGER_ID,
                        (
                            "👤 <b>New Start Command</b>\n\n"
                            f"User: {message.from_user.mention}\n"
                            f"ID: <code>{message.from_user.id}</code>"
                        ),
                        parse_mode=ParseMode.HTML,
                    )

                except Exception:
                    LOGGER.exception("Start logging failed.")

        except Exception:

            LOGGER.exception("Start handler failed.")

            await message.reply_text(
                "❌ Unable to load start menu."
            )

    @app.on_message(
        filters.command("start") & filters.group
    )
    async def group_start(client, message):

        try:

            await add_chat(message.chat.id)

            me = await client.get_me()

            caption = (
                f"🎧 <b>{html.escape(BOT_NAME)}</b>\n\n"
                f"Welcome to {html.escape(message.chat.title or 'Group')}!\n\n"
                "🎵 I am ready to play music in your "
                "group voice chat.\n\n"
                "Use /play to start music.\n"
                "Use /help to see all commands."
            )

            keyboard = get_start_keyboard(
                me.username or ""
            )

            if START_IMAGE:

                try:

                    await message.reply_photo(
                        photo=START_IMAGE,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                    )
                    return

                except Exception:
                    LOGGER.exception("Group start image failed.")

            await message.reply_text(
                caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )

        except Exception:

            LOGGER.exception("Group start failed.")

            await message.reply_text(
                "🎧 Music bot is ready! Use /play to start."
            )

    @app.on_message(
        filters.command("help")
    )
    async def help_command(client, message):

        await send_help(message)

    @app.on_callback_query(
        filters.regex("^help_cmd$")
    )
    async def help_callback(client, query: CallbackQuery):

        await query.answer()

        try:

            await query.message.edit_caption(
                caption=HELP_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=get_help_keyboard(),
            )

        except MessageNotModified:
            pass

        except Exception:

            try:

                await query.message.edit_text(
                    HELP_TEXT,
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_help_keyboard(),
                )

            except Exception:
                LOGGER.exception("Help callback failed.")

    @app.on_callback_query(
        filters.regex("^start_home$")
    )
    async def home_callback(client, query: CallbackQuery):

        await query.answer()

        try:

            me = await client.get_me()

            keyboard = get_start_keyboard(
                me.username or ""
            )

            await query.message.edit_caption(
                caption=START_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )

        except MessageNotModified:
            pass

        except Exception:

            try:

                await query.message.edit_text(
                    START_TEXT,
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_start_keyboard(
                        (await client.get_me()).username or ""
                    ),
                )

            except Exception:
                LOGGER.exception("Home callback failed.")
