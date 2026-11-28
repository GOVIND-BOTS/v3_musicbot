import asyncio
import logging
import random
import time

from pyrogram import filters
from pyrogram.errors import FloodWait, RPCError

LOGGER = logging.getLogger(__name__)

RAID_STR = [
    "HAYEE MERI JAAN 🤩🤩",
    "MERI JAAN KITNI OSM HAI YAAR 😁🌹🌹😍😍😍",
    "I LOVE YOU MERI JAAN ❤️❤️",
    "MERI JAAN I KISS YOU ❤️😋😊😘😘😘",
    "I MISS YOU JAAN 🥀🥀✨✨",
    "Mat muskurao itna ki phoolon ko khabar lag jaye, ke wo kare taareef tumhari aur tumhe unki nazar lag jaye ❤️",
    "Chand se haseen hai chandni, chandni se haseen hai raat; raat se haseen hai chand aur chand se haseen hain aap 🌙",
    "You look so beautiful and pretty. I feel lucky because you love me. I love you now and I’ll always do ❤️",
    "Chand sa tera masoom chehra, tu haya ki ek murat hai 🌹",
    "Kaise karun bayaan main khoobsurati uski, maine to use bina dekhe hi pyaar kiya hai ❤️",
    "Mai tumhari saadgi ki kya misaal doon, is saare jahaan mein bemisaal ho tum ✨",
    "LOVE YOU JAAN 😁😁🔥🔥",
    "I HUG YOU BABY 🤗❤️",
    "I LOVE YOU SO MUCH 🌹💫💖",
    "Hello meri jaan 😍",
    "Oye baby, suno na 😍",
    "I love you babe 😘",
    "Tum hi ho 🥺❤️",
    "Aap hi ke bina hum kyun bechain hain, aap hi kyun meri zaroorat hain ❤️",
    "Oye hoye, sharma gayi kya? Phone kaat di, mummy aa gayi kya? 🤣",
    "Tu maan meri jaan, tujhe jaane na dunga ❤️",
    "Tujhe apni baahon mein saja ke rakhunga 🥰",
    "Hey you... you are so beautiful! I love you 🌹",
    "Meri jaan, tujhe nazar na lag jaaye kisi ki 🧿",
    "Kitna sona tujhe Rab ne banaya, ji kare dekhta rahun ❤️",
    "Lal dupatta ud gaya, haye meri beauty se 🤣",
    "I WANT YOU 👀 BABY",
    "Ummmmaaah meri jaan 😘😘😘",
]

_active = {}
_last_sent = {}
_COOLDOWN_SECONDS = 20


def _target_from_message(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    return None


def register_loveraid_handlers(app):
    @app.on_message(filters.command("loveraid") & (filters.group | filters.private))
    async def activate_loveraid(client, message):
        if message.from_user is None:
            return

        target = _target_from_message(message)
        if target is None:
            args = message.text.split(maxsplit=1)
            if len(args) < 2 or not args[1].strip():
                await message.reply_text(
                    "Reply to a user's message with /loveraid, or use /loveraid @username."
                )
                return
            query = args[1].strip().split()[0]
            try:
                target = await client.get_users(query)
            except (RPCError, ValueError) as exc:
                await message.reply_text(f"User not found: {exc}")
                return

        if target.is_bot:
            await message.reply_text("Love mode cannot be activated for bots.")
            return

        chat_targets = _active.setdefault(message.chat.id, {})
        if target.id in chat_targets:
            await message.reply_text(
                f"❤️ Love mode is already active for {target.mention}."
            )
            return

        chat_targets[target.id] = message.from_user.id
        _last_sent.pop((message.chat.id, target.id), None)
        await message.reply_text(
            f"❤️ Love mode activated for {target.mention}!\n"
            "A random love message will be sent occasionally when they chat.\n"
            "Use /dlove to deactivate."
        )

    @app.on_message(filters.command("dlove") & (filters.group | filters.private))
    async def deactivate_loveraid(client, message):
        if message.from_user is None:
            return

        target = _target_from_message(message)
        if target is None:
            args = message.text.split(maxsplit=1)
            if len(args) < 2 or not args[1].strip():
                await message.reply_text(
                    "Reply to the target's message with /dlove, or use /dlove @username."
                )
                return
            query = args[1].strip().split()[0]
            try:
                target = await client.get_users(query)
            except (RPCError, ValueError) as exc:
                await message.reply_text(f"User not found: {exc}")
                return

        chat_targets = _active.get(message.chat.id, {})
        if target.id not in chat_targets:
            await message.reply_text(f"Love mode is not active for {target.mention}.")
            return

        del chat_targets[target.id]
        _last_sent.pop((message.chat.id, target.id), None)
        if not chat_targets:
            _active.pop(message.chat.id, None)

        await message.reply_text(f"💔 Love mode deactivated for {target.mention}.")

    @app.on_message(
        (filters.group | filters.private)
        & filters.incoming
        & ~filters.bot
        & ~filters.command(["loveraid", "dlove"])
    )
    async def loveraid_replies(client, message):
        user = message.from_user
        if user is None:
            return

        chat_targets = _active.get(message.chat.id)
        if not chat_targets or user.id not in chat_targets:
            return

        key = (message.chat.id, user.id)
        now = time.monotonic()
        if now - _last_sent.get(key, 0) < _COOLDOWN_SECONDS:
            return

        _last_sent[key] = now
        try:
            await message.reply_text(
                random.choice(RAID_STR),
                quote=True,
                disable_web_page_preview=True,
            )
        except FloodWait as exc:
            _last_sent[key] = time.monotonic()
            LOGGER.warning("Love reply rate-limited by Telegram for %s seconds", exc.value)
        except RPCError:
            LOGGER.exception("Could not send loveraid reply in chat %s", message.chat.id)
