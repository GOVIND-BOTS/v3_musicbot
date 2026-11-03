
import logging
import re
from datetime import datetime, timedelta, timezone

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatPermissions

from config import OWNER_ID, SUDO_USERS
from database.mongodb import (
    add_moderation_warning,
    get_moderation_data,
    reset_moderation_warnings,
)

LOGGER = logging.getLogger(__name__)

# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

MAX_WARNINGS = 7
MUTE_MINUTES = 10

# Add or remove words according to your group rules.
# Keep complete words/phrases here to reduce false positives.
BLOCKED_WORDS = {
    "idiot",
    "stupid",
    "fool",
    "loser",
    "shut up",
    "bastard",
}

RULES_TEXT = """
<b>🛡️ STUDENT GROUP SAFETY RULES</b>

━━━━━━━━━━━━━━━━━━

1. Respect every group member.
2. Abusive language is not allowed.
3. Harassment and bullying are prohibited.
4. Inappropriate stickers and media are not allowed.
5. Do not disturb or target other students.
6. Follow the group admins' instructions.

━━━━━━━━━━━━━━━━━━

<b>⚠️ AUTOMATIC MODERATION</b>

• Violating messages may be deleted.
• Each violation adds one warning.
• 1–6 warnings: 10-minute mute.
• 7 warnings: Permanent group ban.

<b>Stay respectful. Keep this group safe.</b>
"""

# --------------------------------------------------
# OWNER / SUDO
# --------------------------------------------------

def get_privileged_users():
    privileged = set()

    if isinstance(OWNER_ID, int):
        privileged.add(OWNER_ID)

    elif isinstance(OWNER_ID, (list, tuple, set)):
        privileged.update(
            user_id for user_id in OWNER_ID
            if isinstance(user_id, int)
        )

    if isinstance(SUDO_USERS, int):
        privileged.add(SUDO_USERS)

    elif isinstance(SUDO_USERS, (list, tuple, set)):
        privileged.update(
            user_id for user_id in SUDO_USERS
            if isinstance(user_id, int)
        )

    return privileged


PRIVILEGED_USERS = get_privileged_users()


# --------------------------------------------------
# TEXT NORMALIZATION
# --------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Normalize text to detect abusive words despite
    uppercase/lowercase and punctuation differences.
    """

    text = text.casefold()

    text = re.sub(r"[^a-z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text


def contains_abuse(text: str) -> bool:
    if not text:
        return False

    normalized = normalize_text(text)

    if not normalized:
        return False

    words = set(normalized.split())

    for blocked in BLOCKED_WORDS:
        blocked_normalized = normalize_text(blocked)

        if not blocked_normalized:
            continue

        if " " in blocked_normalized:
            if blocked_normalized in normalized:
                return True

        elif blocked_normalized in words:
            return True

    return False


# --------------------------------------------------
# ADMIN CHECK
# --------------------------------------------------

async def is_exempt_user(client, chat_id: int, user_id: int) -> bool:
    if user_id in PRIVILEGED_USERS:
        return True

    try:
        member = await client.get_chat_member(chat_id, user_id)

        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )

    except Exception as error:
        LOGGER.warning(
            "Could not check admin status for %s in %s: %s",
            user_id,
            chat_id,
            error,
        )
        return False


# --------------------------------------------------
# MESSAGE DELETION
# --------------------------------------------------

async def delete_violation(message):
    try:
        await message.delete()
        return True

    except Exception as error:
        LOGGER.warning(
            "Could not delete violating message: %s",
            error,
        )
        return False


# --------------------------------------------------
# MUTE USER
# --------------------------------------------------

async def mute_user(client, chat_id: int, user_id: int):
    try:
        until_date = datetime.now(timezone.utc) + timedelta(
            minutes=MUTE_MINUTES
        )

        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_invite_users=True,
            can_pin_messages=False,
            can_change_info=False,
        )

        await client.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=permissions,
            until_date=until_date,
        )

        return True

    except Exception as error:
        LOGGER.error(
            "Failed to mute user %s in %s: %s",
            user_id,
            chat_id,
            error,
        )
        return False


# --------------------------------------------------
# BAN USER
# --------------------------------------------------

async def ban_user(client, chat_id: int, user_id: int):
    try:
        await client.ban_chat_member(
            chat_id=chat_id,
            user_id=user_id,
        )
        return True

    except Exception as error:
        LOGGER.error(
            "Failed to ban user %s in %s: %s",
            user_id,
            chat_id,
            error,
        )
        return False


# --------------------------------------------------
# MODERATION ACTION
# --------------------------------------------------

async def process_violation(client, message, reason: str):
    if not message.from_user:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Never moderate bots or privileged members.
    if message.from_user.is_bot:
        return

    if await is_exempt_user(client, chat_id, user_id):
        return

    deleted = await delete_violation(message)

    if not deleted:
        return

    try:
        warnings = await add_moderation_warning(
            chat_id,
            user_id,
        )

    except Exception:
        LOGGER.exception("Could not save moderation warning.")
        return

    user_mention = message.from_user.mention

    if warnings >= MAX_WARNINGS:
        banned = await ban_user(
            client,
            chat_id,
            user_id,
        )

        if banned:
            text = (
                "🚫 <b>USER BANNED</b>\n\n"
                f"👤 User: {user_mention}\n"
                f"⚠️ Warnings: {warnings}/{MAX_WARNINGS}\n"
                f"📝 Reason: {reason}\n\n"
                "<b>Repeated violations are not allowed.</b>"
            )
        else:
            text = (
                "⚠️ <b>BAN FAILED</b>\n\n"
                f"👤 User: {user_mention}\n"
                f"⚠️ Warnings: {warnings}/{MAX_WARNINGS}\n"
                "Please check the bot's admin permissions."
            )

    else:
        muted = await mute_user(
            client,
            chat_id,
            user_id,
        )

        if muted:
            mute_status = f"🔇 Muted for {MUTE_MINUTES} minutes."
        else:
            mute_status = (
                "⚠️ Mute failed. Please check the bot's "
                "admin permissions."
            )

        text = (
            "⚠️ <b>GROUP RULE VIOLATION</b>\n\n"
            f"👤 User: {user_mention}\n"
            f"⚠️ Warning: {warnings}/{MAX_WARNINGS}\n"
            f"📝 Reason: {reason}\n\n"
            f"{mute_status}\n\n"
            f"🚫 At {MAX_WARNINGS} warnings, "
            "the user will be banned."
        )

    try:
        await client.send_message(
            chat_id,
            text,
            disable_web_page_preview=True,
        )

    except Exception:
        LOGGER.exception("Could not send moderation notice.")


# --------------------------------------------------
# TEXT MODERATION
# --------------------------------------------------

async def moderate_text(client, message):
    if not message.from_user:
        return

    text = message.text or message.caption or ""

    if contains_abuse(text):
        await process_violation(
            client,
            message,
            "Abusive language",
        )


# --------------------------------------------------
# RULES COMMAND
# --------------------------------------------------

async def rules_command(client, message):
    await message.reply_text(
        RULES_TEXT,
        disable_web_page_preview=True,
    )


# --------------------------------------------------
# WARNING COUNT COMMAND
# --------------------------------------------------

async def warnings_command(client, message):
    if not message.from_user:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    # Admins can check another user's warnings by reply.
    target = (
        message.reply_to_message.from_user
        if message.reply_to_message
        else message.from_user
    )

    if not target:
        return

    if target.id != user_id:
        if not await is_exempt_user(client, chat_id, user_id):
            await message.reply_text(
                "❌ Only group admins can check another "
                "member's warnings."
            )
            return

    try:
        data = await get_moderation_data(
            chat_id,
            target.id,
        )

        warnings = data.get("warnings", 0)

        await message.reply_text(
            "🛡️ <b>MODERATION RECORD</b>\n\n"
            f"👤 User: {target.mention}\n"
            f"⚠️ Warnings: {warnings}/{MAX_WARNINGS}"
        )

    except Exception:
        LOGGER.exception("Could not retrieve warnings.")
        await message.reply_text(
            "❌ Could not retrieve moderation records."
        )


# --------------------------------------------------
# RESET WARNINGS COMMAND
# --------------------------------------------------

async def reset_warnings_command(client, message):
    if not message.from_user:
        return

    if not await is_exempt_user(
        client,
        message.chat.id,
        message.from_user.id,
    ):
        await message.reply_text(
            "❌ Only group admins can reset warnings."
        )
        return

    target = (
        message.reply_to_message.from_user
        if message.reply_to_message
        else None
    )

    if not target:
        await message.reply_text(
            "Reply to a user's message with /resetwarns."
        )
        return

    try:
        await reset_moderation_warnings(
            message.chat.id,
            target.id,
        )

        await message.reply_text(
            "✅ <b>Warnings reset successfully.</b>\n\n"
            f"👤 User: {target.mention}\n"
            "⚠️ Warnings: 0"
        )

    except Exception:
        LOGGER.exception("Could not reset warnings.")
        await message.reply_text(
            "❌ Could not reset warnings."
        )


# --------------------------------------------------
# REGISTER HANDLERS
# --------------------------------------------------

def register_handlers(app):
    """
    Register student protection handlers on the Pyrogram client.
    Call this function once during bot startup.
    """

    group_filter = filters.group

    app.on_message(
        group_filter
        & (filters.text | filters.caption)
        & ~filters.command(
            ["rules", "warns", "resetwarns"]
        )
    )(moderate_text)

    app.on_message(
        group_filter
        & filters.command("rules")
    )(rules_command)

    app.on_message(
        group_filter
        & filters.command("warns")
    )(warnings_command)

    app.on_message(
        group_filter
        & filters.command("resetwarns")
    )(reset_warnings_command)

    LOGGER.info("Student protection handlers registered.")
