
import logging
import re

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import OWNER_ID, SUDO_USERS

LOGGER = logging.getLogger(__name__)

# --------------------------------------------------
# MODERATION SETTINGS
# --------------------------------------------------

WARNING_IMAGE = (
    "https://graph.org/file/f1642d89107eeb0b29366-76e447a7d1784059ce.jpg"
)

OWNER_USERS = set(SUDO_USERS)
OWNER_USERS.add(OWNER_ID)

MAX_WARNINGS = 5

# Warning counter (resets when bot restarts).
WARNINGS = {}

# Normal stickers and GIFs are allowed.
BLOCK_STICKERS = False
BLOCK_GIFS = False

BAD_WORDS = {
    "bc",
    "bkl",
    "bklol",
    "bsdk",
    "bhosdike",
    "bhosdi",
    "chutiya",
    "chutiye",
    "gandu",
    "gaand",
    "madarchod",
    "mc",
    "behenchod",
    "bhenchod",
    "lodu",
    "lawde",
    "lund",
    "randi",
    "harami",
    "kamina",
    "kamini",
    "fuck",
    "fucking",
    "motherfucker",
    "bitch",
    "asshole",
    "bastard",
}

BAD_PHRASES = {
    "maa ki",
    "teri maa",
    "teri behen",
    "your mother",
}

# --------------------------------------------------
# GROUP RULES
# --------------------------------------------------

RULES_TEXT = """
📜 𝐆𝐑𝐎𝐔𝐏 𝐑𝐔𝐋𝐄𝐒

━━━━━━━━━━━━━━━━━━

𝟏. Respect every member of the group.
𝟐. Abusive language and offensive words are not allowed.
𝟑. Harassment and threatening behavior are prohibited.
𝟒. Spam and unwanted promotions are not allowed.
𝟓. Explicit stickers and GIFs are prohibited.
𝟔. Always follow the instructions of group admins.

━━━━━━━━━━━━━━━━━━

⚠️ 𝐖𝐀𝐑𝐍𝐈𝐍𝐆 𝐒𝐘𝐒𝐓𝐄𝐌

• First 5 violations: Warnings.
• 6th violation: Permanent group ban.

━━━━━━━━━━━━━━━━━━

𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐛𝐲 𝐆𝐎𝐕𝐈𝐍𝐃 𝐁𝐎𝐓𝐒
"""

# --------------------------------------------------
# BUTTONS
# --------------------------------------------------

def rules_buttons():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📜 𝐆𝐑𝐎𝐔𝐏 𝐑𝐔𝐋𝐄𝐒",
                    callback_data="moderation_rules"
                )
            ],
            [
                InlineKeyboardButton(
                    "📢 𝐆𝐎𝐕𝐈𝐍𝐃 𝐁𝐎𝐓𝐒",
                    url="https://t.me/GOVIND_BOTS"
                )
            ],
        ]
    )


def warning_buttons():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📜 𝐑𝐄𝐀𝐃 𝐆𝐑𝐎𝐔𝐏 𝐑𝐔𝐋𝐄𝐒",
                    callback_data="moderation_rules"
                )
            ]
        ]
    )


# --------------------------------------------------
# TEXT NORMALIZATION
# --------------------------------------------------

def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def contains_abuse(text):
    if not text:
        return False

    normalized = normalize_text(text)
    words = set(normalized.split())

    if words.intersection(BAD_WORDS):
        return True

    for phrase in BAD_PHRASES:
        if phrase in normalized:
            return True

    return False


# --------------------------------------------------
# ADMIN CHECK
# --------------------------------------------------

async def is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(
            chat_id,
            user_id
        )

        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )

    except Exception:
        LOGGER.exception("Admin check failed")

        # Fail safely: never ban if admin status is unknown.
        return True


# --------------------------------------------------
# RULES COMMAND
# --------------------------------------------------

async def rules_command(client, message):
    try:
        await message.reply_text(
            RULES_TEXT,
            reply_markup=rules_buttons(),
            disable_web_page_preview=True,
        )

    except Exception:
        LOGGER.exception("Rules command failed")


# --------------------------------------------------
# RULES CALLBACK
# --------------------------------------------------

async def moderation_callback(client, callback_query):
    if callback_query.data != "moderation_rules":
        return

    try:
        await callback_query.answer(
            "Group Rules",
            show_alert=False
        )

        await callback_query.message.reply_text(
            RULES_TEXT,
            reply_markup=rules_buttons(),
            disable_web_page_preview=True,
        )

    except Exception:
        LOGGER.exception("Rules callback failed")


# --------------------------------------------------
# WARNING MESSAGE
# --------------------------------------------------

async def send_warning(
    client,
    message,
    reason,
    warning_count,
    admin=False
):
    user = message.from_user
    chat_id = message.chat.id

    if admin:
        caption = (
            f"⚠️ 𝐀𝐃𝐌𝐈𝐍 𝐖𝐀𝐑𝐍𝐈𝐍𝐆\n\n"
            f"👤 Member: {user.mention}\n"
            f"⚠️ Reason: {reason}\n\n"
            "Please follow the group rules."
        )
    else:
        caption = (
            f"⚠️ 𝐆𝐑𝐎𝐔𝐏 𝐖𝐀𝐑𝐍𝐈𝐍𝐆\n\n"
            f"👤 Member: {user.mention}\n"
            f"⚠️ Reason: {reason}\n"
            f"🔢 Warning: {warning_count}/{MAX_WARNINGS}\n\n"
            "Please do not repeat this violation.\n"
            "Read the group rules using the button below."
        )

    try:
        await client.send_photo(
            chat_id=chat_id,
            photo=WARNING_IMAGE,
            caption=caption,
            reply_markup=warning_buttons(),
        )

    except Exception:
        LOGGER.exception("Warning image failed")

        try:
            await client.send_message(
                chat_id,
                caption,
                reply_markup=warning_buttons(),
            )
        except Exception:
            LOGGER.exception("Text warning failed")


# --------------------------------------------------
# MODERATION FILTER
# --------------------------------------------------

async def moderation_filter(client, message):
    if not message.from_user:
        return

    user = message.from_user
    user_id = user.id
    chat_id = message.chat.id

    if user.is_bot:
        return

    # Owner and sudo users are exempt.
    if user_id in OWNER_USERS:
        return

    text = message.text or message.caption or ""

    if not contains_abuse(text):
        return

    reason = "Abusive language"

    # Delete violating message.
    try:
        await message.delete()
    except Exception:
        LOGGER.exception("Message deletion failed")

    # Check admin status.
    admin = await is_admin(
        client,
        chat_id,
        user_id
    )

    if admin:
        await send_warning(
            client,
            message,
            reason,
            0,
            admin=True
        )
        return

    # Increase warning count.
    warning_key = (chat_id, user_id)

    WARNINGS[warning_key] = (
        WARNINGS.get(warning_key, 0) + 1
    )

    warning_count = WARNINGS[warning_key]

    # First five violations: warning.
    if warning_count <= MAX_WARNINGS:
        await send_warning(
            client,
            message,
            reason,
            warning_count
        )
        return

    # Sixth violation: ban.
    try:
        await client.ban_chat_member(
            chat_id,
            user_id
        )

        LOGGER.info(
            "User %s banned from chat %s",
            user_id,
            chat_id
        )

        await client.send_photo(
            chat_id=chat_id,
            photo=WARNING_IMAGE,
            caption=(
                f"🚫 𝐔𝐒𝐄𝐑 𝐁𝐀𝐍𝐍𝐄𝐃\n\n"
                f"👤 Member: {user.mention}\n"
                f"⚠️ Reason: Repeated rule violations\n"
                f"🔢 Total warnings: {warning_count}\n\n"
                "This member has been banned "
                "for repeatedly violating group rules."
            ),
            reply_markup=warning_buttons(),
        )

    except Exception:
        LOGGER.exception("User ban failed")

        await send_warning(
            client,
            message,
            reason,
            warning_count
        )


# --------------------------------------------------
# REGISTER HANDLERS
# --------------------------------------------------

def register_moderation_handlers(app):

    # Rules command.
    app.on_message(
        filters.command("rules") & filters.group
    )(rules_command)

    # Rules button.
    app.on_callback_query(
        filters.regex("^moderation_rules$")
    )(moderation_callback)

    # Only text and captions are checked.
    # No sticker/GIF blocking.
    app.on_message(
        filters.group & (filters.text | filters.caption)
    )(moderation_filter)

    LOGGER.info(
        "Moderation handlers registered successfully"
    )
