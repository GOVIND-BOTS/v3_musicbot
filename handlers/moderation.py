
import logging
import re

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import OWNER_ID, SUDO_USERS

LOGGER = logging.getLogger(__name__)

# --------------------------------------------------
# WELCOME IMAGES
# --------------------------------------------------

WELCOME_IMAGE = (
    "https://graph.org/file/f1642d89107eeb0b29366-76e447a7d1784059ce.jpg"
)

OWNER_WELCOME_IMAGE = (
    "https://graph.org/file/b42e5363bf36860f18d1b-56144a16a15b23c77c.jpg"
)

OWNER_USERS = set(SUDO_USERS)
OWNER_USERS.add(OWNER_ID)

# --------------------------------------------------
# MODERATION SETTINGS
# --------------------------------------------------

# True = सभी stickers और GIFs ब्लॉक होंगे।
# Telegram bot अपने आप केवल अश्लील sticker/GIF पहचान नहीं सकता।
BLOCK_STICKERS = True
BLOCK_GIFS = True

# गाली-गलौज की सूची। जरूरत के अनुसार इसमें शब्द जोड़ सकते हो।
BAD_WORDS = {
    "bc",
    "bkl",
    "bklol",
    "bsdk",
    "bhosdike",
    "bhosdi",
    "chutiya",
    "chutiye",
    "chutiya",
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

RULES_TEXT = """
**📜 GOVIND BOTS RULES**

Group में सभी members इन नियमों का पालन करें।

1. किसी भी member को गाली देना मना है।
2. किसी को परेशान या धमकी न दें।
3. Spam और unwanted promotion न करें।
4. अश्लील GIF और stickers की अनुमति नहीं है।
5. Group में सभी members का सम्मान करें।
6. Admin के instructions का पालन करें।

⚠️ Rules तोड़ने पर moderation action लिया जा सकता है।

**— GOVIND BOTS**
"""

# --------------------------------------------------
# BUTTONS
# --------------------------------------------------

def rules_buttons():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📜 RULES",
                    callback_data="moderation_rules"
                ),
                InlineKeyboardButton(
                    "👑 OWNER",
                    url=f"tg://user?id={OWNER_ID}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📢 GOVIND BOTS",
                    url="https://t.me/GOVIND_BOTS"
                )
            ],
        ]
    )


# --------------------------------------------------
# TEXT NORMALIZATION
# --------------------------------------------------

def normalize_text(text):
    text = text.lower()

    # Extra spaces और punctuation हटाना
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def contains_abuse(text):
    if not text:
        return False

    normalized = normalize_text(text)
    words = set(normalized.split())

    # Exact word matching, ताकि सामान्य शब्दों पर
    # गलती से moderation action न हो।
    if words.intersection(BAD_WORDS):
        return True

    # Common abusive phrases
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
        return False


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
# RULES BUTTON CALLBACK
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
# MODERATION FILTER
# --------------------------------------------------

async def moderation_filter(client, message):
    if not message.from_user:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    # Bot messages को ignore करो
    if message.from_user.is_bot:
        return

    # Admins और Owner को ban नहीं करना।
    admin = await is_admin(
        client,
        chat_id,
        user_id
    )

    violation = False
    reason = ""

    # Text moderation
    text = message.text or message.caption or ""

    if text and contains_abuse(text):
        violation = True
        reason = "गाली-गलौज"

    # Sticker moderation
    elif BLOCK_STICKERS and message.sticker:
        violation = True
        reason = "Sticker भेजना"

    # GIF / Animation moderation
    elif BLOCK_GIFS and message.animation:
        violation = True
        reason = "GIF भेजना"

    if not violation:
        return

    # Admin को सिर्फ warning
    if admin:
        try:
            await message.reply_text(
                f"⚠️ {message.from_user.mention}, "
                f"कृपया {reason} से बचें।"
            )
        except Exception:
            LOGGER.exception("Admin warning failed")

        return

    # Member का violating message delete करो
    try:
        await message.delete()
    except Exception:
        LOGGER.exception("Message deletion failed")

    # Warning
    try:
        await client.send_message(
            chat_id,
            (
                f"⚠️ {message.from_user.mention}\n\n"
                f"आपका message नियमों के विरुद्ध था।\n"
                f"कारण: **{reason}**\n\n"
                "आपको group से ban किया जा रहा है।"
            )
        )
    except Exception:
        LOGGER.exception("Moderation warning failed")

    # Ban member
    try:
        await client.ban_chat_member(
            chat_id,
            user_id
        )

        LOGGER.info(
            "Banned user %s from chat %s",
            user_id,
            chat_id
        )

    except Exception:
        LOGGER.exception(
            "Could not ban user %s from chat %s",
            user_id,
            chat_id
        )


# --------------------------------------------------
# NEW MEMBER WELCOME
# --------------------------------------------------

async def welcome_new_member(client, update):
    try:
        old_member = update.old_chat_member
        new_member = update.new_chat_member

        if not new_member or not new_member.user:
            return

        user = new_member.user

        if user.is_bot:
            return

        # केवल नए join पर welcome भेजना
        if old_member:
            if old_member.status not in (
                ChatMemberStatus.LEFT,
                ChatMemberStatus.BANNED,
            ):
                return

        if new_member.status not in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
            ChatMemberStatus.RESTRICTED,
        ):
            return

        is_owner = user.id in OWNER_USERS

        image = (
            OWNER_WELCOME_IMAGE
            if is_owner
            else WELCOME_IMAGE
        )

        if is_owner:
            caption = (
                f"👑 **SPECIAL OWNER ARRIVAL**\n\n"
                f"Welcome {user.mention}!\n\n"
                "**GOVIND BOTS** में आपका स्वागत है।\n"
                "✨ Special Owner/Sudo Member"
            )
        else:
            caption = (
                f"🎵 **WELCOME TO V3 MUSIC**\n\n"
                f"Hello {user.mention}!\n\n"
                "Group में आपका स्वागत है। ❤️\n\n"
                "📜 कृपया Group Rules पढ़ें।\n\n"
                "**Powered by GOVIND-BOTS**"
            )

        await client.send_photo(
            chat_id=update.chat.id,
            photo=image,
            caption=caption,
            reply_markup=rules_buttons(),
        )

    except Exception:
        LOGGER.exception("Welcome handler failed")


# --------------------------------------------------
# REGISTER ALL HANDLERS
# --------------------------------------------------

def register_moderation_handlers(app):

    # Rules command
    app.on_message(
        filters.command("rules") & filters.group
    )(rules_command)

    # Rules button
    app.on_callback_query(
        filters.regex("^moderation_rules$")
    )(moderation_callback)

    # Text, stickers and GIF moderation
    moderation_filter_types = filters.group & (
        filters.text
        | filters.caption
        | filters.sticker
        | filters.animation
    )

    app.on_message(
        moderation_filter_types
    )(moderation_filter)

    # New member welcome
    app.on_chat_member_updated(
        filters.group
    )(welcome_new_member)

    LOGGER.info("Moderation handlers registered successfully")
