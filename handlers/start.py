
import html
import logging
from urllib.parse import urlparse

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)

from config import (
    START_IMAGE,
    SUPPORT_CHAT,
    SUPPORT_CHANNEL,
    OWNER_ID,
    BOT_NAME,
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
        "Select a category to see its commands and usage.\n\n"
        "🎵 Music & playback\n"
        "🛡 Group admin tools\n"
        "🧰 Group utilities\n"
        "🤖 Babu AI chat\n"
        "🔒 Private whisper\n\n"
        "<i>Commands work in groups unless stated otherwise.</i>"
    )


HELP_PAGES = {
    "music": (
        "🎵 <b>MUSIC COMMANDS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "▶️ <code>/play song name</code> — Play audio\n"
        "🎬 <code>/vplay song name</code> — Play video\n"
        "💬 <code>adisha play song</code> — Play audio\n"
        "💬 <code>adisha vplay song</code> — Play video\n"
        "💬 <code>babu play song</code> / <code>baby play song</code>\n"
        "💬 <code>babu vplay song</code> / <code>baby vplay song</code>\n"
        "👤 <code>/joinuserbot</code> — Add/check assistant in group\n\n"
        "<i>Play is audio; vplay is video. Use in a group.</i>"
    ),

    "playback": (
        "🎛 <b>PLAYBACK & QUEUE</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⏸ <code>/pause</code> — Pause (group admin)\n"
        "▶️ <code>/resume</code> — Resume (group admin)\n"
        "⏭ <code>skip</code> — Skip current track (group admin)\n"
        "⏭ <code>adisha skip</code> / <code>baby skip</code>\n"
        "⏹ <code>/stop</code> — Stop playback (group admin)\n"
        "📜 <code>/queue</code> — Show queued songs\n"
        "🎶 <code>/now</code> — Show current song\n"
        "🧹 <code>/clearqueue</code> — Clear queue and stop\n\n"
        "<i>The player card also has pause, resume, replay, "
        "skip, stop and queue buttons.</i>"
    ),

    "admin": (
        "🛡 <b>GROUP ADMIN COMMANDS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Reply to a user's message, then send one of these:\n\n"
        "🚫 <code>adisa ban</code> / <code>boom</code> — Ban\n"
        "♻️ <code>adisa unban</code> — Unban\n"
        "👢 <code>adisa kick</code> / <code>out</code> / "
        "<code>nikal</code> — Kick\n"
        "🔇 <code>adisa mute</code> / <code>silent</code> / "
        "<code>shut</code> — Mute\n"
        "🔊 <code>adisa unmute</code> / <code>speak</code> / "
        "<code>free</code> — Unmute\n"
        "⬆️ <code>adisa promote</code> / "
        "<code>adminship</code> — Promote\n"
        "⬇️ <code>adisa demote</code> / "
        "<code>lelo</code> — Demote\n\n"
        "Aliases: <code>adisa</code>, <code>disa</code>, "
        "<code>disha</code> (also accepts <code>/</code> "
        "and <code>!</code> prefixes).\n"
        "<i>Only group admins can use these actions.</i>"
    ),

    "tools": (
        "🧰 <b>GROUP & UTILITY TOOLS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📣 <code>/tagall</code> — Mention group members\n"
        "📣 <code>/all</code> / <code>/tagmember</code> — Tag aliases\n"
        "🛑 <code>/cancel</code> — Cancel an active tag process\n"
        "🌐 <code>/tr</code> — Translate a replied-to text\n\n"
        "<b>Translation examples</b>\n"
        "<code>/tr hi</code> — Translate to Hindi\n"
        "<code>/tr en</code> — Translate to English\n"
        "<code>/tr en//hi</code> — Translate Hindi to English\n\n"
        "<i>For /tr, reply to the message you want translated. "
        "Tag commands require group admin rights.</i>"
    ),

    "chat": (
        "🤖 <b>BABU AI CHAT</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "💬 <code>ask your question</code> — Ask Babu\n"
        "💬 <code>babu your question</code> — Ask Babu\n"
        "💬 <code>adisha your question</code> — Ask Babu\n"
        "💬 <code>adisa your question</code> — Ask Babu\n\n"
        "<b>Enable group chat mode</b>\n"
        "• <code>babu chat on</code>\n"
        "• <code>babu baat kro</code> / <code>babu baat karo</code>\n"
        "• <code>babu enable chat</code>\n"
        "• <code>babu start chat</code> / <code>babu chat start</code>\n\n"
        "<b>Disable group chat mode</b>\n"
        "• <code>babu chat off</code>\n"
        "• <code>babu baat band karo</code>\n"
        "• <code>babu chup ho jao</code>\n"
        "• <code>babu disable chat</code>\n"
        "• <code>babu stop chat</code> / <code>babu chat stop</code>\n\n"
        "<i>Only group admins can switch group chat mode on or off. "
        "Requires GEMINI_API_KEY.</i>"
    ),

    "whisper": (
        "🔒 <b>PRIVATE WHISPER</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Use the bot's inline mode in any chat:\n\n"
        "<code>@BOT_USERNAME username your message</code>\n"
        "or\n"
        "<code>@BOT_USERNAME user_id your message</code>\n\n"
        "The inline results provide two options:\n"
        "🔒 <b>Open Whisper</b> — Can be opened more than once\n"
        "🔥 <b>One-Time Whisper</b> — Removed after recipient reads it\n\n"
        "<i>Replace BOT_USERNAME with this bot's username. "
        "Inline mode must be enabled in BotFather.</i>"
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
        links.append(
            InlineKeyboardButton("💬 SUPPORT", url=support)
        )

    if updates:
        links.append(
            InlineKeyboardButton("📢 UPDATES", url=updates)
        )

    if links:
        rows.append(links)

    rows.append([
        InlineKeyboardButton(
            "🎧 HELP CENTER",
            callback_data="help_cmd",
        ),
        InlineKeyboardButton(
            "👑 OWNER",
            url=f"tg://user?id={OWNER_ID}",
        ),
    ])

    return InlineKeyboardMarkup(rows)


def get_help_keyboard(page="home"):
    if page == "home":
        rows = [
            [
                InlineKeyboardButton(
                    "🎵 MUSIC",
                    callback_data="help_music",
                ),
                InlineKeyboardButton(
                    "🎛 PLAYBACK",
                    callback_data="help_playback",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🛡 ADMIN",
                    callback_data="help_admin",
                ),
                InlineKeyboardButton(
                    "🧰 TOOLS",
                    callback_data="help_tools",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🤖 BABU AI",
                    callback_data="help_chat",
                ),
                InlineKeyboardButton(
                    "🔒 WHISPER",
                    callback_data="help_whisper",
                ),
            ],
        ]

    else:
        rows = [
            [
                InlineKeyboardButton(
                    "⬅️ BACK",
                    callback_data="help_cmd",
                ),
                InlineKeyboardButton(
                    "🏠 HOME",
                    callback_data="start_home",
                ),
                InlineKeyboardButton(
                    "✖ CLOSE",
                    callback_data="ctrl_close",
                ),
            ]
        ]

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

        except Exception:
            LOGGER.exception("Menu edit failed.")


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
            LOGGER.warning(
                "Start image could not be sent; using text.",
                exc_info=True,
            )

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
        duration = html.escape(
            str(info.get("duration_text") or "Unknown")
        )

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
            f'<a href="{html.escape(url, quote=True)}">'
            "🔗 Watch on YouTube</a>\n\n"
            f"💖 <b>{html.escape(BOT_NAME)}</b>"
        )

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
            await status.edit_text(
                "❌ Could not retrieve YouTube information."
            )

        except Exception:
            LOGGER.exception("Could not update video info status.")


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

        except Exception as exc:
            LOGGER.exception("Start handler failed.")

            await message.reply_text(
                f"❌ Start Error: {type(exc).__name__}\n"
                f"<code>{html.escape(str(exc)[:300])}</code>",
                parse_mode=ParseMode.HTML,
            )

    @app.on_message(filters.command("start") & filters.group)
    async def group_start(client, message):
        try:
            await add_chat(message.chat.id)

            me = await client.get_me()

            caption = (
                f"👑 <b>{html.escape(BOT_NAME)}</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"Welcome to "
                f"<b>{html.escape(message.chat.title or 'your group')}</b>!\n\n"
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
                    LOGGER.warning(
                        "Group start image failed; using text.",
                        exc_info=True,
                    )

            await message.reply_text(
                caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

        except Exception:
            LOGGER.exception("Group start failed.")

            await message.reply_text(
                "🎧 Music bot is ready! Use /play to start."
            )

    @app.on_message(filters.command("help"))
    async def help_command(client, message):
        try:
            await send_help(message)

        except Exception:
            LOGGER.exception("Help command failed.")

    @app.on_callback_query(filters.regex(r"^help_cmd$"))
    async def help_callback(client, query: CallbackQuery):
        await query.answer()

        await _edit_menu(
            query,
            _help_home_text(),
            get_help_keyboard("home"),
        )

    @app.on_callback_query(
        filters.regex(
            r"^help_(music|playback|admin|tools|chat|whisper)$"
        )
    )
    async def help_section_callback(client, query: CallbackQuery):
        page = query.data.split("_", 1)[1]

        await query.answer()

        await _edit_menu(
            query,
            HELP_PAGES[page],
            get_help_keyboard(page),
        )

    @app.on_callback_query(filters.regex(r"^start_home$"))
    async def home_callback(client, query: CallbackQuery):
        await query.answer()

        me = await client.get_me()

        await _edit_menu(
            query,
            _start_text(),
            get_start_keyboard(me.username or ""),
        )
