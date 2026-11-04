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

SOURCE_VIDEO = "https://graph.org/file/353b45128ff9e8412698e-4e0ae8dafee5eb951b.mp4"


def _safe_url(value):
    value = str(value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme in ("https", "http") and parsed.netloc:
        return value
    return None


def _start_text():
    name = html.escape(BOT_NAME or "GOVIND MUSIC")
    return (
        f"🍃ᶦϻᷧ) <b>{name}</b> 🍃\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎧 𝐌ᴜsɪᴄ 𝐏ʟᴀʏᴇʀ 𝐖ɪᴛʜ 𝐂ʟᴏɴᴇ 𝐅ᴇᴀᴛᴜʀᴇs\n"
        "🤖 𝐂ʀᴇᴀᴛᴇ 𝐘ᴏᴜʀ 𝐎ᴡɴ 𝐁ᴏᴛ 𝐈ɴsᴛᴀɴᴛʟʏ\n"
        "⚡ 𝟸𝟺/𝟽 𝐀ᴄᴛɪᴠᴇ | ★ 𝐏ʀᴇᴍɪᴜᴍ 𝐐ᴜᴀʟɪᴛʏ\n"
        "❓ 𝐂ʟɪᴄᴋ 𝐇ᴇʟᴘ 𝐅ᴏʀ 𝐌ᴏᴅᴜʟᴇs & 𝐂ᴏᴍᴍᴀɴᴅs\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )


def _help_home_text():
    return (
        "🍃 <b>𝐂ʜᴏᴏsᴇ 𝐀 𝐂ᴀᴛᴇɢᴏʀʏ 𝐅ᴏʀ 𝐇ᴇʟᴘ</b>\n\n"
        "❓ 𝐀sᴋ 𝐘ᴏᴜʀ 𝐃ᴏᴜʙᴛs 𝐈ɴ 𝐒ᴜᴘᴘᴏʀᴛ 𝐂ʜᴀᴛ\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✦ 𝐀ʟʟ 𝐂ᴏᴍᴍᴀɴᴅs 𝐔sᴇ 𝐏ʀᴇғɪx : /"
    )


def _source_text():
    return (
        "🍃 <b>𝐒ᴏᴜʀᴄᴇ 𝐂ᴏᴅᴇ</b> 🍃\n\n"
        "𝐓ʜɪs 𝐁ᴏᴛ's 𝐒ᴏᴜʀᴄᴇ ɪs 𝐏ʀɪᴠᴀᴛᴇ.\n"
        "𝐂ᴏɴᴛᴀᴄᴛ 𝐓ʜᴇ 𝐎ᴡɴᴇʀ ɪғ 𝐘ᴏᴜ 𝐍ᴇᴇᴅ 𝐈ᴛ.\n\n"
        "👑 𝐓ᴀᴘ 𝐓ʜᴇ 𝐁ᴜᴛᴛᴏɴ 𝐁ᴇʟᴏᴡ 𝐓ᴏ 𝐂ᴏɴᴛᴀᴄᴛ 𝐎ᴡɴᴇʀ."
    )


HELP_PAGES = {
    "admin": (
        "<b>👮 𝐀ᴅᴍɪɴ 𝐂ᴏᴍᴍᴀɴᴅs</b>\n\n"
        "<code>/pause</code> — 𝐏ᴀᴜsᴇ 𝐓ʜᴇ 𝐂ᴜʀʀᴇɴᴛ 𝐒ᴛʀᴇᴀᴍ.\n"
        "<code>/resume</code> — 𝐑ᴇsᴜᴍᴇ 𝐓ʜᴇ 𝐏ᴀᴜsᴇᴅ 𝐒ᴛʀᴇᴀᴍ.\n"
        "<code>/skip</code> — 𝐒ᴋɪᴘ 𝐓ʜᴇ 𝐂ᴜʀʀᴇɴᴛ 𝐓ʀᴀᴄᴋ.\n"
        "<code>/stop</code> — 𝐂ʟᴇᴀʀ 𝐐ᴜᴇᴜᴇ & 𝐒ᴛᴏᴘ 𝐒ᴛʀᴇᴀᴍ.\n"
        "<code>/player</code> — 𝐎ᴘᴇɴ 𝐏ʟᴀʏᴇʀ 𝐏ᴀɴᴇʟ.\n"
        "<code>/queue</code> — 𝐒ʜᴏᴡ 𝐐ᴜᴇᴜᴇ 𝐋ɪsᴛ."
    ),
    "auth": (
        "<b>🔐 𝐀ᴜᴛʜ 𝐂ᴏᴍᴍᴀɴᴅs</b>\n\n"
        "<code>/auth</code> — 𝐀ᴅᴅ 𝐔sᴇʀ 𝐓ᴏ 𝐀ᴜᴛʜ 𝐋ɪsᴛ.\n"
        "<code>/unauth</code> — 𝐑ᴇᴍᴏᴠᴇ 𝐔sᴇʀ 𝐅ʀᴏᴍ 𝐀ᴜᴛʜ.\n"
        "<code>/authusers</code> — 𝐒ʜᴏᴡ 𝐀ᴜᴛʜ 𝐔sᴇʀs."
    ),
    "play": (
        "<b>🎵 𝐏ʟᴀʏ 𝐂ᴏᴍᴍᴀɴᴅs</b>\n\n"
        "<code>/play</code> — 𝐏ʟᴀʏ 𝐘ᴏᴜʀ 𝐑ᴇǫᴜᴇsᴛᴇᴅ 𝐒ᴏɴɢ.\n"
        "<code>/vplay</code> — 𝐏ʟᴀʏ 𝐕ɪᴅᴇᴏ 𝐒ᴏɴɢ.\n"
        "<code>/cplay</code> — 𝐏ʟᴀʏ 𝐈ɴ 𝐂ʜᴀɴɴᴇʟ."
    ),
    "loop": (
        "<b>🔁 𝐋ᴏᴏᴘ 𝐂ᴏᴍᴍᴀɴᴅs</b>\n\n"
        "<code>/loop</code> — 𝐄ɴᴀʙʟᴇ / 𝐃ɪsᴀʙʟᴇ 𝐋ᴏᴏᴘ."
    ),
    "shuffle": (
        "<b>🔀 𝐒ʜᴜғғʟᴇ 𝐐ᴜᴇᴜᴇ</b>\n\n"
        "<code>/shuffle</code> — 𝐒ʜᴜғғʟᴇ 𝐓ʜᴇ 𝐐ᴜᴇᴜᴇ."
    ),
    "seek": (
        "<b>⏩ 𝐒ᴇᴇᴋ 𝐂ᴏᴍᴍᴀɴᴅs</b>\n\n"
        "<code>/seek</code> — 𝐒ᴇᴇᴋ 𝐂ᴜʀʀᴇɴᴛ 𝐒ᴛʀᴇᴀᴍ."
    ),
    "song": (
        "<b>🎶 𝐒ᴏɴɢ 𝐃ᴏᴡɴʟᴏᴀᴅ</b>\n\n"
        "<code>/song</code> — 𝐃ᴏᴡɴʟᴏᴀᴅ 𝐀ᴜᴅɪᴏ 𝐓ʀᴀᴄᴋ.\n"
        "<code>/video</code> — 𝐃ᴏᴡɴʟᴏᴀᴅ 𝐕ɪᴅᴇᴏ 𝐓ʀᴀᴄᴋ."
    ),
    "speed": (
        "<b>⚡ 𝐒ᴘᴇᴇᴅ 𝐂ᴏᴍᴍᴀɴᴅs</b>\n\n"
        "<code>/speed</code> — 𝐂ʜᴀɴɢᴇ 𝐏ʟᴀʏʙᴀᴄᴋ 𝐒ᴘᴇᴇᴅ."
    ),
    "ping": (
        "<b>📡 𝐏ɪɴɢ</b>\n\n"
        "<code>/ping</code> — 𝐂ʜᴇᴄᴋ 𝐁ᴏᴛ 𝐏ɪɴɢ & 𝐒ʏsᴛᴇᴍ 𝐒ᴛᴀᴛs."
    ),
    "gban": (
        "<b>🛡 𝐆ʟᴏʙᴀʟ 𝐁ᴀɴ</b>\n\n"
        "<code>/gban</code> — 𝐆ʟᴏʙᴀʟʟʏ 𝐁ᴀɴ 𝐀 𝐔sᴇʀ.\n"
        "<code>/ungban</code> — 𝐑ᴇᴍᴏᴠᴇ 𝐆ʟᴏʙᴀʟ 𝐁ᴀɴ."
    ),
    "broadcast": (
        "<b>📢 𝐁ʀᴏᴀᴅᴄᴀsᴛ</b>\n\n"
        "<code>/broadcast</code> — 𝐒ᴇɴᴅ 𝐌ᴇssᴀɢᴇ 𝐓ᴏ 𝐀ʟʟ 𝐂ʜᴀᴛs."
    ),
}


def get_start_keyboard(bot_username):
    rows = []

    if bot_username:
        rows.append([
            InlineKeyboardButton(
                "➕ 𝐀ᴅᴅ 𝐌ᴇ 𝐓ᴏ 𝐆ʀᴏᴜᴘ",
                url=f"https://t.me/{bot_username}?startgroup=true",
            )
        ])

    rows.append([
        InlineKeyboardButton("👑 𝐎ᴡɴᴇʀ", url=f"tg://user?id={OWNER_ID}"),
        InlineKeyboardButton("🧬 𝐂ʟᴏɴᴇ", url="https://t.me/Adishax_music_bot"),
    ])

    support = _safe_url(SUPPORT_CHAT)
    third_row = []
    if support:
        third_row.append(InlineKeyboardButton("💬 𝐒ᴜᴘᴘᴏʀᴛ", url=support))

    third_row.append(InlineKeyboardButton("📦 𝐒ᴏᴜʀᴄᴇ", callback_data="source_menu"))

    if third_row:
        rows.append(third_row)

    rows.append([
        InlineKeyboardButton("🎧 𝐇ᴇʟᴘ & 𝐂ᴏᴍᴍᴀɴᴅs", callback_data="help_cmd")
    ])

    return InlineKeyboardMarkup(rows)


def get_source_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👑 𝐎ᴡɴᴇʀ", url=f"tg://user?id={OWNER_ID}"),
            InlineKeyboardButton("🔙 𝐁ᴀᴄᴋ", callback_data="start_home"),
        ]
    ])


def get_help_keyboard(page="home"):
    if page == "home":
        rows = [
            [
                InlineKeyboardButton("👮 𝐀ᴅᴍɪɴ", callback_data="help_admin"),
                InlineKeyboardButton("🔐 𝐀ᴜᴛʜ", callback_data="help_auth"),
                InlineKeyboardButton("📢 𝐆-𝐂ᴀsᴛ", callback_data="help_broadcast"),
            ],
            [
                InlineKeyboardButton("🚫 𝐁ʟ-𝐂ʜᴀᴛ", callback_data="help_gban"),
                InlineKeyboardButton("👤 𝐁ʟ-𝐔sᴇʀ", callback_data="help_gban"),
                InlineKeyboardButton("▶️ 𝐂-𝐏ʟᴀʏ", callback_data="help_play"),
            ],
            [
                InlineKeyboardButton("🛡 𝐆-𝐁ᴀɴ", callback_data="help_gban"),
                InlineKeyboardButton("🔁 𝐋ᴏᴏᴘ", callback_data="help_loop"),
                InlineKeyboardButton("⏩ 𝐀ᴜᴛᴏ-𝐏ʟᴀʏ", callback_data="help_play"),
            ],
            [
                InlineKeyboardButton("📡 𝐏ɪɴɢ", callback_data="help_ping"),
                InlineKeyboardButton("🎵 𝐏ʟᴀʏ", callback_data="help_play"),
                InlineKeyboardButton("🔀 𝐒ʜᴜғғʟᴇ", callback_data="help_shuffle"),
            ],
            [
                InlineKeyboardButton("⏩ 𝐒ᴇᴇᴋ", callback_data="help_seek"),
                InlineKeyboardButton("🎶 𝐒ᴏɴɢ", callback_data="help_song"),
                InlineKeyboardButton("⚡ 𝐒ᴘᴇᴇᴅ", callback_data="help_speed"),
            ],
            [
                InlineKeyboardButton("🔙 𝐁ᴀᴄᴋ", callback_data="start_home"),
            ],
        ]
    else:
        rows = [
            [
                InlineKeyboardButton("🔙 𝐁ᴀᴄᴋ", callback_data="help_cmd"),
                InlineKeyboardButton("❌ 𝐂ʟᴏsᴇ", callback_data="ctrl_close"),
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

    anim_msg = await message.reply_text("🍃")
    await asyncio.sleep(0.4)
    await anim_msg.edit_text("🍃 𝐒ᴛᴀʀᴛɪɴɢ...")
    await asyncio.sleep(0.4)
    await anim_msg.edit_text("💚 𝐒ᴛᴀʀᴛɪɴɢ...")
    await asyncio.sleep(0.4)
    await anim_msg.edit_text("✨ 𝐀ʟᴍᴏsᴛ 𝐑ᴇᴀᴅʏ...")
    await asyncio.sleep(0.5)
    await anim_msg.delete()

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
                f"🍃 𝐓ʜɪs ɪs <b>{html.escape(BOT_NAME)}</b> 🍃\n"
                f"✨ 𝐖ᴇʟᴄᴏᴍᴇ 𝐓ᴏ <b>{html.escape(message.chat.title or 'Group')}</b>!\n\n"
                "🎧 𝐔sᴇ /play 𝐓ᴏ 𝐒ᴛᴀʀᴛ 𝐌ᴜsɪᴄ."
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

    @app.on_callback_query(filters.regex(r"^source_menu$"))
    async def source_menu_callback(client, query: CallbackQuery):
        await query.answer()
        try:
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
            LOGGER.warning(f"Source video failed: {e}")
            await client.send_message(
                chat_id=query.message.chat.id,
                text=_source_text(),
                parse_mode=ParseMode.HTML,
                reply_markup=get_source_keyboard(),
            )

    @app.on_callback_query(filters.regex(r"^help_cmd$"))
    async def help_callback(client, query: CallbackQuery):
        await query.answer()
        await _edit_menu(query, _help_home_text(), get_help_keyboard("home"))

    @app.on_callback_query(filters.regex(r"^help_(admin|auth|play|loop|shuffle|seek|song|speed|ping|gban|broadcast)$"))
    async def help_section_callback(client, query: CallbackQuery):
        page = query.data.split("_", 1)[1]
        await query.answer()
        text = HELP_PAGES.get(page, "𝐍ᴏ 𝐈ɴғᴏʀᴍᴀᴛɪᴏɴ 𝐀ᴠᴀɪʟᴀʙʟᴇ.")
        await _edit_menu(query, text, get_help_keyboard(page))

    @app.on_callback_query(filters.regex(r"^start_home$"))
    async def home_callback(client, query: CallbackQuery):
        await query.answer()
        me = await client.get_me()
        try:
            await query.message.delete()
        except Exception:
            pass

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
