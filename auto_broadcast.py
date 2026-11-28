import asyncio
import logging
import os
import random
from pathlib import Path

from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_NAME, OWNER_ID, START_IMAGE, SUPPORT_CHAT
from database.mongodb import get_chats, remove_chat

LOGGER = logging.getLogger("v3_musicbot.auto_broadcast")

INTERVAL_HOURS = max(1.0, float(os.getenv("AUTO_BROADCAST_INTERVAL_HOURS", "1")))
INTERVAL_SECONDS = INTERVAL_HOURS * 60 * 60
BANNER_PATH = Path(__file__).resolve().parent / "assets" / "v3music-banner..png"

PROMO_MESSAGES = (
    (
        "🎧 <b>{name} — MUSIC PLAYBACK</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎵 <code>/play song name</code> — YouTube se audio search karke voice chat mein play karein.\n"
        "🎬 <code>/vplay song name</code> — supported video playback.\n"
        "⏸ Pause  •  ▶️ Resume  •  ⏭ Skip  •  ⏹ Stop\n"
        "📜 <code>/queue</code> — upcoming songs dekhein.\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Bot ko apne doston ke group mein bhi add karein!"
    ),
    (
        "✨ <b>YOUR GROUP, YOUR MUSIC BOARD</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎶 YouTube music search & voice-chat playback\n"
        "🔀 Queue Shuffle aur 🔁 Loop controls\n"
        "🎛 Player board se Pause, Resume, Skip aur Stop\n"
        "🖼 Custom music thumbnail aur requester display\n"
        "📖 <code>/help</code> se commands aur usage dekhein.\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Enjoy music together with <b>{name}</b>!"
    ),
    (
        "🔥 <b>LET'S PLAY SOME MUSIC!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ Group voice chat start karein.\n"
        "2️⃣ <code>/play Arijit Singh</code> bhejein.\n"
        "3️⃣ Song queue mein add hoga aur playback start hoga.\n"
        "4️⃣ <code>/queue</code> se next songs dekhein.\n"
        "5️⃣ Admins playback ko Pause, Resume, Skip ya Stop kar sakte hain.\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Need help? <code>/help</code> use karein."
    ),
    (
        "💎 <b>{name} — MUSIC FEATURES</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎧 Audio playback: <code>/play</code>\n"
        "🎥 Video playback: <code>/vplay</code>\n"
        "📃 Queue: <code>/queue</code>\n"
        "🔁 Repeat: <code>/loop</code>\n"
        "🔀 Shuffle: <code>/shuffle</code>\n"
        "⏯ Playback controls player board par available hain.\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Bot ko apne group mein add karke music enjoy karein!"
    ),
)


def _keyboard(bot_username):
    rows = []
    if bot_username:
        rows.append([
            InlineKeyboardButton(
                "➕ ADD MUSIC BOT TO GROUP",
                url=f"https://t.me/{bot_username}?startgroup=true",
            )
        ])

    rows.append([
        InlineKeyboardButton("👑 OWNER", url=f"tg://user?id={OWNER_ID}"),
        InlineKeyboardButton("📖 HELP", url=f"https://t.me/{bot_username}?start=help")
        if bot_username else InlineKeyboardButton("📖 HELP", callback_data="help_cmd"),
    ])

    support = str(SUPPORT_CHAT or "").strip()
    if support.startswith(("https://", "http://")):
        rows.append([InlineKeyboardButton("💬 SUPPORT", url=support)])

    return InlineKeyboardMarkup(rows)


async def _send_promo(client, chat_id, bot_username):
    caption = random.choice(PROMO_MESSAGES).format(name=BOT_NAME or "V3 MUSIC")
    keyboard = _keyboard(bot_username)

    if START_IMAGE:
        try:
            await client.send_photo(
                chat_id,
                photo=START_IMAGE,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
            return
        except Exception:
            LOGGER.debug("Configured promo image failed in %s", chat_id, exc_info=True)

    if BANNER_PATH.is_file():
        try:
            await client.send_photo(
                chat_id,
                photo=str(BANNER_PATH),
                caption=caption,
                reply_markup=keyboard,
            )
            return
        except Exception:
            LOGGER.debug("Local promo banner failed in %s", chat_id, exc_info=True)

    await client.send_message(
        chat_id,
        text=caption,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


async def auto_broadcast_loop(client):
    """Send one rotating feature announcement to every registered group per interval."""
    me = await client.get_me()
    bot_username = me.username or ""
    LOGGER.info(
        "Auto-promo broadcast enabled: interval=%s hours",
        INTERVAL_HOURS,
    )

    while True:
        await asyncio.sleep(INTERVAL_SECONDS)
        try:
            chat_ids = await get_chats()
        except Exception:
            LOGGER.exception("Could not load registered group list for auto broadcast")
            continue

        sent = 0
        removed = 0
        for chat_id in chat_ids:
            try:
                await _send_promo(client, chat_id, bot_username)
                sent += 1
                await asyncio.sleep(0.25)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error_name = type(exc).__name__
                LOGGER.warning(
                    "Auto broadcast failed for chat %s: %s: %s",
                    chat_id, error_name, exc,
                )
                if error_name in {
                    "ChatWriteForbidden",
                    "PeerIdInvalid",
                    "UserBannedInChannel",
                    "ChannelPrivate",
                }:
                    try:
                        await remove_chat(chat_id)
                        removed += 1
                    except Exception:
                        LOGGER.exception("Could not remove unavailable chat %s", chat_id)

        LOGGER.info(
            "Auto broadcast cycle completed: sent=%s unavailable_removed=%s total=%s",
            sent, removed, len(chat_ids),
        )
