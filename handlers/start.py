import html
import logging
import asyncio
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


LOGGER = logging.getLogger(__name__)

# ==================== SOURCE MENU VIDEO ====================
# Yahan apna source menu ka video link daalo (Telegram file_id ya direct link)
SOURCE_VIDEO = "https://graph.org/file/your-source-video.mp4"   # ← yahan apna video daalo


def _safe_url(value):
    value = str(value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme in ("https", "http") and parsed.netloc:
        return value
    return None


def _start_text():
    name = html.escape(BOT_NAME or "GOVIND MUSIC")
    return (
        f"✦ THIS IS ✿ <b>{name}</b> ✿ ✦ ♫ !\n"
        "========================================\n"
        "✦ 🎧 MUSIC PLAYER WITH CLONE FEATURES\n"
        "✦ 🤖 CREATE YOUR OWN BOT INSTANTLY\n"
        "✦ ⚡ 24x7 ACTIVE | ★ PREMIUM QUALITY\n"
        "✦ ❓ CLICK ON THE HELP BUTTON TO GET INFO\n"
        "   ABOUT MY MODULES AND COMMANDS...!\n"
        "========================================"
    )


def _help_home_text():
    return (
        "✦ <b>CHOOSE THE CATEGORY FOR WHICH YOU WANNA GET HELP.</b>\n"
        "❓ ASK YOUR DOUBTS AT ✦ SUPPORT CHAT\n"
        "ALL COMMANDS CAN BE USED WITH : /"
    )


def _source_text():
    return (
        "✦ <b>SOURCE CODE</b> ✦\n\n"
        "Yeh bot ka source private hai.\n"
        "Agar aapko source chahiye to Owner se contact karein.\n\n"
        "👑 Owner se baat karne ke liye neeche button dabayein."
    )


HELP_PAGES = {
    "admin": (
        "<b>ADMIN COMMANDS :</b>\n\n"
        "<code>/pause</code> — Pause the current playing stream.\n"
        "<code>/resume</code> — Resume the paused stream.\n"
        "<code>/skip</code> — Skip the current playing stream.\n"
        "<code>/stop</code> — Clears the queue and end stream.\n"
        "<code>/player</code> — Get interactive player panel.\n"
        "<code>/queue</code> — Shows the queued tracks list."
    ),
    "auth": (
        "<b>AUTH COMMANDS :</b>\n\n"
        "<code>/auth</code> — Add a user to auth list.\n"
        "<code>/unauth</code> — Remove a user from auth list.\n"
        "<code>/authusers</code> — Show all auth users."
    ),
    "play": (
        "<b>PLAY COMMANDS :</b>\n\n"
        "<code>/play</code> — Play the requested song.\n"
        "<code>/vplay</code> — Play video song.\n"
        "<code>/cplay</code> — Play in channel."
    ),
    "loop": (
        "<b>LOOP COMMANDS :</b>\n\n"
        "<code>/loop</code> — Enable/Disable loop."
    ),
    "shuffle": (
        "<b>SHUFFLE QUEUE :</b>\n\n"
        "<code>/shuffle</code> — Shuffle the queue list."
    ),
    "seek": (
        "<b>SEEK COMMANDS :</b>\n\n"
        "<code>/seek</code> — Seek the current playing stream."
    ),
    "song": (
        "<b>SONG DOWNLOAD :</b>\n\n"
        "<code>/song</code> — Download track in audio.\n"
        "<code>/video</code> — Download track in video."
    ),
    "speed": (
        "<b>SPEED COMMANDS :</b>\n\n"
        "<code>/speed</code> — Change the playback speed."
    ),
    "ping": (
        "<b>PING :</b>\n\n"
        "<code>/ping</code> — Check bot ping & system stats."
    ),
    "gban": (
        "<b>GLOBAL BAN :</b>\n\n"
        "<code>/gban</code> — Globally ban a user.\n"
        "<code>/ungban</code> — Remove global ban."
    ),
    "broadcast": (
        "<b>BROADCAST :</b>\n\n"
        "<code>/broadcast</code> — Broadcast message to all chats."
    ),
}


def get_start_keyboard(bot_username):
    rows = []

    if bot_username:
        rows.append([
            InlineKeyboardButton(
                "➕ ADD ME TO YOUR GROUP",
                url=f"https://t.me/{bot_username}?startgroup=true",
            )
        ])

    rows.append([
        InlineKeyboardButton("👑 OWNER", url=f"tg://user?id={OWNER_ID}"),
        InlineKeyboardButton("🧬 CLONE", url="https://t.me/YOUR_CLONE_BOT"),  # ← apna clone bot daalo
    ])

    support = _safe_url(SUPPORT_CHAT)
    third_row = []
    if support:
        third_row.append(InlineKeyboardButton("💬 SUPPORT", url=support))
    
    # SOURCE ab callback se khulega (repo link nahi)
    third_row.append(InlineKeyboardButton("📦 SOURCE", callback_data="source_menu"))

    if third_row:
        rows.append(third_row)

    rows.append([
        InlineKeyboardButton("🎧 HELP AND COMMANDS", callback_data="help_cmd")
    ])

    return InlineKeyboardMarkup(rows)


def get_source_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👑 OWNER", url=f"tg://user?id={OWNER_ID}"),
            InlineKeyboardButton("🔙 BACK", callback_data="start_home"),
        ]
    ])


def get_help_keyboard(page="home"):
    if page == "home":
        rows = [
            [
                InlineKeyboardButton("👮 ADMIN", callback_data="help_admin"),
                InlineKeyboardButton("🔐 AUTH", callback_data="help_auth"),
                InlineKeyboardButton("📢 G-CAST", callback_data="help_broadcast"),
            ],
            [
                InlineKeyboardButton("🚫 BL-CHAT", callback_data="help_gban"),
                InlineKeyboardButton("👤 BL-USER", callback_data="help_gban"),
                InlineKeyboardButton("▶️ C-PLAY", callback_data="help_play"),
            ],
            [
                InlineKeyboardButton("🛡 G-BAN", callback_data="help_gban"),
                InlineKeyboardButton("🔁 LOOP", callback_data="help_loop"),
                InlineKeyboardButton("⏩ AUTO-PLAY", callback_data="help_play"),
            ],
            [
                InlineKeyboardButton("📡 PING", callback_data="help_ping"),
                InlineKeyboardButton("🎵 PLAY", callback_data="help_play"),
                InlineKeyboardButton("🔀 SHUFFLE", callback_data="help_shuffle"),
            ],
            [
                InlineKeyboardButton("⏩ SEEK", callback_data="help_seek"),
                InlineKeyboardButton("🎶 SONG", callback_data="help_song"),
                InlineKeyboardButton("⚡ SPEED", callback_data="help_speed"),
            ],
            [
                InlineKeyboardButton("🔙 BACK", callback_data="start_home"),
            ],
        ]
    else:
        rows = [
            [
                InlineKeyboardButton("🔙 BACK", callback_data="help_cmd"),
                InlineKeyboardButton("❌ CLOSE", callback_data="ctrl_close"),
            ]
        ]
    return InlineKeyboardMarkup(rows)


async def _edit_menu(query, text, keyboard):
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

    # ========== ANIMATION START ==========
    anim_msg = await message.reply_text("❤️")
    await asyncio.sleep(0.4)
    await anim_msg.edit_text("❤️ STARTING...")
    await asyncio.sleep(0.4)
    await anim_msg.edit_text("💖 STARTING...")
    await asyncio.sleep(0.4)
    await anim_msg.edit_text("💓 ALMOST READY...")
    await asyncio.sleep(0.5)
    await anim_msg.delete()
    # ====================================

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
            LOGGER.warning("Start image failed", exc_info=True)

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


def register_start_handlers(app):

    @app.on_message(filters.command("start") & filters.private)
    async def start_command(client, message):
        try:
            args = (message.text or "").split(maxsplit=1)
            if len(args) > 1 and args[1].strip() == "help":
                return await send_help(message)
            await send_start(client, message)
        except Exception as exc:
            LOGGER.exception("Start handler failed.")
            await message.reply_text(f"❌ Error: {exc}")

    @app.on_message(filters.command("start") & filters.group)
    async def group_start(client, message):
        try:
            await add_chat(message.chat.id)
            me = await client.get_me()
            caption = (
                f"✦ THIS IS ✿ <b>{html.escape(BOT_NAME)}</b> ✿ ✦\n"
                f"Welcome to <b>{html.escape(message.chat.title or 'Group')}</b>!\n\n"
                "Use /play to start music."
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
                    pass
            await message.reply_text(caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception:
            LOGGER.exception("Group start failed.")

    @app.on_message(filters.command("help"))
    async def help_command(client, message):
        await send_help(message)

    # ==================== SOURCE MENU ====================
    @app.on_callback_query(filters.regex(r"^source_menu$"))
    async def source_menu_callback(client, query: CallbackQuery):
        await query.answer()
        try:
            # Pehle purana message delete karke naya video bhej rahe hain
            await query.message.delete()
        except Exception:
            pass

        try:
            await client.send_video(
                chat_id=query.message.chat.id,
                video=SOURCE_VIDEO,
                caption=_source_text(),
                parse_mode=ParseMode.HTML,
                reply_markup=get_source_keyboard(),
            )
        except Exception as e:
            # Agar video fail ho jaye to text bhej do
            LOGGER.warning(f"Source video failed: {e}")
            await client.send_message(
                chat_id=query.message.chat.id,
                text=_source_text(),
                parse_mode=ParseMode.HTML,
                reply_markup=get_source_keyboard(),
            )

    # ==================== HELP CALLBACKS ====================
    @app.on_callback_query(filters.regex(r"^help_cmd$"))
    async def help_callback(client, query: CallbackQuery):
        await query.answer()
        await _edit_menu(query, _help_home_text(), get_help_keyboard("home"))

    @app.on_callback_query(filters.regex(r"^help_(admin|auth|play|loop|shuffle|seek|song|speed|ping|gban|broadcast)$"))
    async def help_section_callback(client, query: CallbackQuery):
        page = query.data.split("_", 1)[1]
        await query.answer()
        text = HELP_PAGES.get(page, "No information available.")
        await _edit_menu(query, text, get_help_keyboard(page))

    @app.on_callback_query(filters.regex(r"^start_home$"))
    async def home_callback(client, query: CallbackQuery):
        await query.answer()
        me = await client.get_me()
        try:
            await query.message.delete()
        except Exception:
            pass

        # Wapas start menu bhejo
        keyboard = get_start_keyboard(me.username or "")
        if START_IMAGE:
            try:
                await client.send_photo(
                    chat_id=query.message.chat.id,
                    photo=START_IMAGE,
                    caption=_start_text(),
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
                return
            except Exception:
                pass

        await client.send_message(
            chat_id=query.message.chat.id,
            text=_start_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )

    @app.on_callback_query(filters.regex(r"^ctrl_close$"))
    async def close_callback(client, query: CallbackQuery):
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
