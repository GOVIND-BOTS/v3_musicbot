
import asyncio
import html
import logging
import os
import re
from urllib.parse import urlparse

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatType, ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import OWNER_ID, WELCOME_IMAGE

LOGGER = logging.getLogger(__name__)

BIO_LINK_PATTERN = re.compile(
    r"(?i)(?:"
    r"(?:https?://)?(?:www\.)?t\.me/[a-zA-Z0-9_+/=-]+"
    r"|(?:https?://)?telegram\.me/[a-zA-Z0-9_+/=-]+"
    r"|(?<![\w])@[a-zA-Z][a-zA-Z0-9_]{3,}"
    r")"
)

scan_locks = {}


def get_owner_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👑 𝐂ᴏɴᴛᴀᴄᴛ 𝐎ᴡɴᴇʀ",
                url=f"tg://user?id={OWNER_ID}"
            )
        ]
    ])


def extract_targets(bio):
    if not bio:
        return []

    return list(dict.fromkeys(
        match.group(0).strip()
        for match in BIO_LINK_PATTERN.finditer(bio)
    ))


def normalize_target(target):
    target = target.strip()

    if target.startswith("@"):
        return target[1:]

    if "t.me/" in target.lower() or "telegram.me/" in target.lower():
        if not target.startswith(("http://", "https://")):
            target = "https://" + target

        parsed = urlparse(target)
        path = parsed.path.strip("/")

        if not path:
            return None

        return path.split("/")[0]

    return None


async def is_external_group_link(assistant, target, current_chat):
    value = normalize_target(target)

    if not value:
        return False

    # Private invite links are treated as external group links.
    if value.startswith("+") or value.lower() == "joinchat":
        return True

    # Ignore the current group's own username.
    if current_chat.username and value.lower() == current_chat.username.lower():
        return False

    try:
        linked_chat = await assistant.get_chat(value)

        if linked_chat.id == current_chat.id:
            return False

        return linked_chat.type in (
            ChatType.GROUP,
            ChatType.SUPERGROUP,
            ChatType.CHANNEL,
        )

    except Exception:
        # Do not flag unresolved @user handles as group/channel links.
        # Explicit t.me invite links are handled above.
        return False


async def get_user_bio(assistant, user_id):
    try:
        user = await assistant.get_users(user_id)
        return user.bio or ""
    except Exception as exc:
        LOGGER.debug("Could not read bio for %s: %s", user_id, exc)
        return ""


async def check_member(client, assistant, chat, user):
    if not user or user.is_bot:
        return False

    bio = await get_user_bio(assistant, user.id)
    targets = extract_targets(bio)

    if not targets:
        return False

    for target in targets:
        if await is_external_group_link(assistant, target, chat):
            await send_warning(client, chat, user)
            return True

    return False


async def send_warning(client, chat, user):
    name = html.escape(
        " ".join(part for part in (user.first_name, user.last_name) if part)
        or "Member"
    )

    username = (
        f"@{html.escape(user.username)}"
        if user.username
        else f'<a href="tg://user?id={user.id}">{name}</a>'
    )

    caption = (
        "⚠️ <b>𝐁ɪᴏ 𝐋ɪɴᴋ 𝐏ᴏʟɪᴄʏ 𝐍ᴏᴛɪᴄᴇ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 𝐌ᴇᴍʙᴇʀ: {username}\n\n"
        "Your Telegram bio appears to contain an external "
        "group/channel link or username.\n\n"
        "Please remove promotional links and external "
        "group/channel usernames from your bio to follow "
        "this group's rules.\n\n"
        "💚 Thank you for your cooperation!\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👑 Contact the Owner if you need assistance."
    )

    markup = get_owner_keyboard()

    try:
        if WELCOME_IMAGE and os.path.isfile(WELCOME_IMAGE):
            await client.send_photo(
                chat.id,
                photo=WELCOME_IMAGE,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        else:
            await client.send_message(
                chat.id,
                caption,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
                disable_web_page_preview=True,
            )

    except Exception:
        LOGGER.exception("Bio warning could not be sent in %s", chat.id)


async def is_group_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


async def scan_group(client, assistant, chat):
    lock = scan_locks.setdefault(chat.id, asyncio.Lock())

    if lock.locked():
        return 0

    flagged = 0

    async with lock:
        try:
            async for member in client.get_chat_members(chat.id):
                user = member.user

                if not user or user.is_bot:
                    continue

                if await check_member(client, assistant, chat, user):
                    flagged += 1

                await asyncio.sleep(0.15)

        except Exception:
            LOGGER.exception("Bio scan failed for %s", chat.id)

    return flagged


def register_bio_guard_handlers(app, assistant):

    @app.on_chat_member_updated(filters.group)
    async def bio_guard_new_member(client, update):
        try:
            new_member = update.new_chat_member
            old_member = update.old_chat_member

            if not new_member:
                return

            if new_member.status not in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.RESTRICTED,
            ):
                return

            if old_member and old_member.status in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.RESTRICTED,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            ):
                return

            user = new_member.user

            await check_member(
                client,
                assistant,
                update.chat,
                user,
            )

        except Exception:
            LOGGER.exception("New member bio check failed.")

    @app.on_message(
        filters.command("checkbio") & filters.group
    )
    async def checkbio_command(client, message):
        if not message.from_user:
            return

        if not await is_group_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text(
                "❌ Only group administrators can use this command."
            )

        status = await message.reply_text(
            "🔍 <b>𝐒ᴄᴀɴɴɪɴɢ 𝐆ʀᴏᴜᴘ 𝐌ᴇᴍʙᴇʀs...</b>",
            parse_mode=ParseMode.HTML,
        )

        flagged = await scan_group(
            client,
            assistant,
            message.chat,
        )

        await status.edit_text(
            "✅ <b>𝐁ɪᴏ 𝐒ᴄᴀɴ 𝐂ᴏᴍᴘʟᴇᴛᴇ</b>\n\n"
            f"⚠️ Members with external group/channel links: "
            f"<b>{flagged}</b>",
            parse_mode=ParseMode.HTML,
        )
