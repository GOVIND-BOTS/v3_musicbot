import html
import logging
from urllib.parse import urlparse

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from config import (
    START_IMAGE,
    SUPPORT_CHAT,
    SUPPORT_CHANNEL,
    OWNER_ID,
    BOT_NAME,
    LOGGER_ID,
)
from database.mongodb import add_user, add_chat
from youtube import get_video_info

LOGGER = logging.getLogger(__name__)


def _safe_url(value):
    value = str(value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme in ("https", "http") and parsed.netloc:
        return value
    return None


def _start_text():
    name = html.escape(BOT_NAME or "GOVIND MUSIC")
    return (
        f"👑 <b>WELCOME TO {name}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎧 <b>Your Royal Music Experience</b>\n\n"
        "🎵 High-quality audio streaming\n"
        "🎬 Video in Telegram voice chats\n"
        "⚡ Fast search & smart queue\n"
        "🎨 Auto-generated music player cards\n"
        "🎛 Easy inline playback controls\n\n"
        "✨ Add me to your group and let the music begin!\n\n"
        "<i>Powered by GOVIND BOTS</i>"
    )


def _help_home_text():
    return (
        "🎧 <b>GOVIND MUSIC — HELP CENTER</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Choose a category below to see its commands.\n\n"
        "🎵 <b>Music:</b> Play and control songs\n"
        "🧰 <b>Group tools:</b> Utility commands\n\n"
        "💡 <i>Commands are shown with the / prefix.</i>"
    )


HELP_PAGES = {
    "music": (
        "🎵 <b>MUSIC COMMANDS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "▶️ <code>/play song name</code> — Play audio\n"
        "🎬 <code>/vplay song name</code> — Play video\n"
        "⏸ <code>/pause</code> — Pause playback (admin)\n"
        "▶️ <code>/resume</code> — Resume playback (admin)\n"
        "⏭ <code>skip</code> — Skip current track (admin)\n"
        "⏹ <code>/stop</code> — Stop playback (admin)\n"
        "📜 <code>/queue</code> — Show upcoming tracks\n"
        "🎶 <code>/now</code> — Show current track\n"
        "🧹 <code>/clearqueue</code> — Clear the queue\n"
        "👤 <code>/joinuserbot</code> — Assistant join command\n\n"
        "<i>Use play/vplay in a group with a voice chat.</i>"
    ),
    "tools": (
        "🧰 <b>GROUP & UTILITY COMMANDS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🌐 <code>/tr</code> — Translate a replied text\n"
        "📣 <code>/tagall</code> — Mention group members\n"
        "🛑 <code>/cancel</code> — Stop active tag process\n"
        "💬 <code>adisa</code> / <code>disa</code> — Group assistant\n\n"
        "<i>Some commands require admin permissions.</i>"
    ),
}


def get_start_keyboard(bot_username):
    rows = []
    if bot_username:
        rows.append([
            InlineKeyboardButton(
                "➕ ADD TO GROUP",
                url=f"https://t.me/{bot_username}?startgroup=true",
            )
        ])

    links = []
    support = _safe_url(SUPPORT_CHAT)
    updates = _safe_url(SUPPORT_CHANNEL)
    if support:
        links.append(InlineKeyboardButton("💬 SUPPORT", url=support))
    if updates:
        links.append(InlineKeyboardButton("📢 UPDATES", url=updates))
    if links:
        rows.append(links)

    rows.append([
        InlineKeyboardButton("🎧 HELP CENTER", callback_data="help_cmd"),
        InlineKeyboardButton("👑 OWNER", user_id=OWNER_ID),
    ])
    return InlineKeyboardMarkup(rows)


def get_help_keyboard(page="home"):
    rows = []
    if page == "home":
        rows.append([
            InlineKeyboardButton("🎵 MUSIC", callback_data="help_music"),
            InlineKeyboardButton("🧰 TOOLS", callback_data="help_tools"),
        ])
    else:
        rows.append([
            InlineKeyboardButton("🎵 MUSIC", callback_data="help_music"),
            InlineKeyboardButton("🧰 TOOLS", callback_data="help_tools"),
        ])
    rows.append([
        InlineKeyboardButton("🏠 HOME", callback_data="start_home"),
        InlineKeyboardButton("✖ CLOSE", callback_data="ctrl_close"),
    ])
    return InlineKeyboardMarkup(rows)


async def _edit_menu(query, text, keyboard):
    """Edit either a photo caption or a normal text message."""
    try:
        await query.message.edit_caption(
            caption=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
    except MessageNotModified:
        return
    except Exception:
        try:
            await query.message.edit_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        except MessageNotModified:
            return


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
                caption=_start_text(),
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
            return
        except Exception:
            LOGGER.warning("Start image could not be sent; using text.", exc_info=True)

    await message.reply_text(
        _start_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


async def send_help(message):
    await message.reply_text(
        _help_home_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=get_help_keyboard("home"),
        disable_web_page_preview=True,
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
        title = html.escape(str(info.get("title") or "Unknown"))
        channel = html.escape(str(info.get("channel") or "Unknown"))
        duration = html.escape(str(info.get("duration_text") or "Unknown"))
        views = info.get("views") or 0
        url = _safe_url(info.get("webpage_url")) or (
            f"https://www.youtube.com/watch?v={video_id}"
        )

        try:
            views_text = f"{int(views):,}"
        except (TypeError, ValueError):
            views_text = "Unknown"

        caption = (
            "🎵 <b>TRACK INFORMATION</b>\n\n"
            f"📌 <b>Title:</b> {title}\n"
            f"⏳ <b>Duration:</b> {duration}\n"
            f"👀 <b>Views:</b> {views_text}\n"
            f"🎤 <b>Channel:</b> {channel}\n\n"
            f'🔗 <a href="{html.escape(url, quote=True)}">Watch on YouTube</a>\n\n'
            f"💖 <b>{html.escape(BOT_NAME)}</b>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶ WATCH ON YOUTUBE", url=url)],
            [InlineKeyboardButton("🏠 HOME", callback_data="start_home")],
        ])
        thumbnail = info.get("thumbnail")
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
                disable_web_page_preview=True,
            )
    except Exception:
        LOGGER.exception("Video information failed.")
        try:
            await status.edit_text("❌ Could not retrieve YouTube information.")
        except Exception:
            pass


def register_start_handlers(app):

    @app.on_message(filters.command("start") & filters.private)
    async def start_command(client, message):
        try:
            args = (message.text or "").split(maxsplit=1)
            if len(args) > 1:
                payload = args[1].strip()
                if payload == "help":
                    return await send_help(message)
                if payload.startswith("info_"):
                    video_id = payload[5:].strip()
                    if video_id:
                        return await send_video_info(client, message, video_id)
                if payload == "verify":
                    return await message.reply_text("✅ Verification successful!")

            await send_start(client, message)

            if LOGGER_ID and message.from_user:
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
            await message.reply_text("❌ Unable to load start menu.")

    @app.on_message(filters.command("start") & filters.group)
    async def group_start(client, message):
        try:
            await add_chat(message.chat.id)
            me = await client.get_me()
            caption = (
                f"👑 <b>{html.escape(BOT_NAME)}</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"Welcome to <b>{html.escape(message.chat.title or 'your group')}</b>!\n\n"
                "🎵 Ready to play music in your voice chat.\n"
                "▶️ Send <code>/play song name</code> for audio.\n"
                "🎬 Send <code>/vplay song name</code> for video.\n"
                "📚 Send <code>/help</code> to view commands."
            )
            keyboard = get_start_keyboard(me.username or "")
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
                    LOGGER.warning("Group start image failed; using text.", exc_info=True)
            await message.reply_text(
                caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        except Exception:
            LOGGER.exception("Group start failed.")
            await message.reply_text("🎧 Music bot is ready! Use /play to start.")

    @app.on_message(filters.command("help"))
    async def help_command(client, message):
        await send_help(message)

    @app.on_callback_query(filters.regex(r"^help_cmd$"))
    async def help_callback(client, query: CallbackQuery):
        await query.answer()
        await _edit_menu(query, _help_home_text(), get_help_keyboard("home"))

    @app.on_callback_query(filters.regex(r"^help_(music|tools)$"))
    async def help_section_callback(client, query: CallbackQuery):
        page = query.data.split("_", 1)[1]
        await query.answer()
        await _edit_menu(query, HELP_PAGES[page], get_help_keyboard(page))

    @app.on_callback_query(filters.regex(r"^start_home$"))
    async def home_callback(client, query: CallbackQuery):
        await query.answer()
        me = await client.get_me()
        await _edit_menu(
            query,
            _start_text(),
            get_start_keyboard(me.username or ""),
        )
