
import asyncio
import logging
import os
import tempfile

from datetime import datetime, timedelta, timezone

import cv2

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)

from nudenet import NudeDetector

from config import OWNER_ID, SUDO_USERS

LOGGER = logging.getLogger(__name__)

# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

WARNING_IMAGE = (
    "https://graph.org/file/f1642d89107eeb0b29366-76e447a7d1784059ce.jpg"
)

MAX_WARNINGS = 5
MUTE_MINUTES = 10

OWNER_USERS = set(SUDO_USERS)
OWNER_USERS.add(OWNER_ID)

WARNINGS = {}

# NudeNet initialization
DETECTOR = NudeDetector()

# Explicit content classes
EXPLICIT_CLASSES = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    "ANUS_EXPOSED",
    "BUTTOCKS_EXPOSED",
}

DETECTION_THRESHOLD = 0.55

# --------------------------------------------------
# RULES
# --------------------------------------------------

RULES_TEXT = """
📜 𝐆𝐑𝐎𝐔𝐏 𝐑𝐔𝐋𝐄𝐒

━━━━━━━━━━━━━━━━━━

1. Respect every member.
2. Abusive language is prohibited.
3. Harassment is not allowed.
4. Spam is prohibited.
5. Explicit stickers and GIFs are prohibited.
6. Follow the group administrators.

━━━━━━━━━━━━━━━━━━

⚠️ 𝐖𝐀𝐑𝐍𝐈𝐍𝐆 𝐒𝐘𝐒𝐓𝐄𝐌

• First 5 violations: Warning + 10-minute mute.
• 6th violation: Permanent ban.

━━━━━━━━━━━━━━━━━━

𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐛𝐲 𝐆𝐎𝐕𝐈𝐍𝐃 𝐁𝐎𝐓𝐒
"""


def rules_buttons():
    return InlineKeyboardMarkup([
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
        ]
    ])


def warning_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📜 𝐑𝐄𝐀𝐃 𝐆𝐑𝐎𝐔𝐏 𝐑𝐔𝐋𝐄𝐒",
                callback_data="moderation_rules"
            )
        ]
    ])


# --------------------------------------------------
# RULES COMMAND
# --------------------------------------------------

async def rules_command(client, message):
    await message.reply_text(
        RULES_TEXT,
        reply_markup=rules_buttons(),
        disable_web_page_preview=True
    )


async def moderation_callback(client, callback_query):
    if callback_query.data != "moderation_rules":
        return

    await callback_query.answer("Group Rules")

    await callback_query.message.reply_text(
        RULES_TEXT,
        reply_markup=rules_buttons()
    )


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
            ChatMemberStatus.OWNER
        )

    except Exception:
        LOGGER.exception("Admin check failed")
        return True


# --------------------------------------------------
# IMAGE NSFW DETECTION
# --------------------------------------------------

def detect_explicit_image(image_path):
    try:
        results = DETECTOR.detect(image_path)

        for result in results:
            label = result.get("class", "")
            score = result.get("score", 0)

            if (
                label in EXPLICIT_CLASSES
                and score >= DETECTION_THRESHOLD
            ):
                LOGGER.info(
                    "Explicit content detected: %s (%.2f)",
                    label,
                    score
                )
                return True

        return False

    except Exception:
        LOGGER.exception("Image detection failed")
        return False


# --------------------------------------------------
# VIDEO / GIF DETECTION
# --------------------------------------------------

def detect_explicit_video(video_path):
    capture = cv2.VideoCapture(video_path)

    if not capture.isOpened():
        return False

    try:
        fps = capture.get(cv2.CAP_PROP_FPS)

        if not fps or fps <= 0:
            fps = 15

        frame_count = int(
            capture.get(cv2.CAP_PROP_FRAME_COUNT)
        )

        duration = frame_count / fps if frame_count else 0

        # Check up to 12 frames across the animation.
        sample_count = min(
            12,
            max(1, int(duration * 2))
        )

        for index in range(sample_count):

            if frame_count:
                position = int(
                    index * frame_count / sample_count
                )

                capture.set(
                    cv2.CAP_PROP_POS_FRAMES,
                    position
                )

            success, frame = capture.read()

            if not success:
                continue

            with tempfile.NamedTemporaryFile(
                suffix=".jpg",
                delete=False
            ) as temp:

                frame_path = temp.name

            try:
                cv2.imwrite(frame_path, frame)

                if detect_explicit_image(frame_path):
                    return True

            finally:
                if os.path.exists(frame_path):
                    os.remove(frame_path)

        return False

    finally:
        capture.release()


# --------------------------------------------------
# MEDIA CLASSIFICATION
# --------------------------------------------------

def classify_media(file_path):
    extension = os.path.splitext(file_path)[1].lower()

    # Static image stickers
    if extension in (
        ".webp",
        ".png",
        ".jpg",
        ".jpeg"
    ):
        return detect_explicit_image(file_path)

    # GIFs and video stickers
    if extension in (
        ".gif",
        ".mp4",
        ".webm",
        ".mkv"
    ):
        return detect_explicit_video(file_path)

    # TGS animated vector stickers need a separate
    # Lottie rendering pipeline.
    LOGGER.warning(
        "Unsupported sticker format: %s",
        extension
    )

    return False


# --------------------------------------------------
# DOWNLOAD AND CHECK MEDIA
# --------------------------------------------------

async def check_media(message):

    media = message.sticker or message.animation

    if not media:
        return False

    filename = getattr(media, "file_name", None) or ""

    extension = os.path.splitext(filename)[1].lower()

    if not extension:
        if message.sticker:
            if getattr(media, "is_animated", False):
                extension = ".tgs"
            elif getattr(media, "is_video", False):
                extension = ".webm"
            else:
                extension = ".webp"
        else:
            extension = ".mp4"

    with tempfile.TemporaryDirectory() as temp_dir:

        file_path = os.path.join(
            temp_dir,
            "moderation_media" + extension
        )

        try:
            downloaded = await message.download(
                file_name=file_path
            )

            if not downloaded:
                return False

            return await asyncio.to_thread(
                classify_media,
                downloaded
            )

        except Exception:
            LOGGER.exception("Media download/check failed")
            return False


# --------------------------------------------------
# WARNING MESSAGE
# --------------------------------------------------

async def send_warning(
    client,
    message,
    warning_count,
    admin=False
):

    user = message.from_user
    chat_id = message.chat.id

    if admin:
        caption = (
            "⚠️ 𝐀𝐃𝐌𝐈𝐍 𝐀𝐋𝐄𝐑𝐓\n\n"
            f"👤 Member: {user.mention}\n"
            "⚠️ Explicit media detected.\n\n"
            "Please follow the group rules."
        )

    else:
        caption = (
            "⚠️ 𝐆𝐑𝐎𝐔𝐏 𝐖𝐀𝐑𝐍𝐈𝐍𝐆\n\n"
            f"👤 Member: {user.mention}\n"
            "⚠️ Reason: Explicit sticker/GIF\n"
            f"🔢 Warning: {warning_count}/{MAX_WARNINGS}\n"
            f"🔇 Mute: {MUTE_MINUTES} minutes\n\n"
            "Explicit media is not allowed.\n"
            "Please follow the group rules."
        )

    try:
        await client.send_photo(
            chat_id,
            WARNING_IMAGE,
            caption=caption,
            reply_markup=warning_buttons()
        )

    except Exception:
        LOGGER.exception("Warning photo failed")

        await client.send_message(
            chat_id,
            caption,
            reply_markup=warning_buttons()
        )


# --------------------------------------------------
# MUTE MEMBER
# --------------------------------------------------

async def mute_user(client, chat_id, user_id):

    until_date = (
        datetime.now(timezone.utc)
        + timedelta(minutes=MUTE_MINUTES)
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
        can_invite_users=False,
        can_pin_messages=False,
        can_change_info=False,
    )

    await client.restrict_chat_member(
        chat_id,
        user_id,
        permissions=permissions,
        until_date=until_date
    )


# --------------------------------------------------
# MAIN MEDIA MODERATION
# --------------------------------------------------

async def moderation_filter(client, message):

    if not message.from_user:
        return

    user = message.from_user
    user_id = user.id
    chat_id = message.chat.id

    if user.is_bot:
        return

    # Owner and sudo exemption
    if user_id in OWNER_USERS:
        return

    # Only stickers and GIFs are processed
    if not (message.sticker or message.animation):
        return

    # Detect explicit content
    is_explicit = await check_media(message)

    if not is_explicit:
        return

    # Delete explicit media
    try:
        await message.delete()

    except Exception:
        LOGGER.exception("Explicit media deletion failed")

    # Admin exemption
    admin = await is_admin(
        client,
        chat_id,
        user_id
    )

    if admin:
        await send_warning(
            client,
            message,
            0,
            admin=True
        )
        return

    # Warning counter
    warning_key = (chat_id, user_id)

    WARNINGS[warning_key] = (
        WARNINGS.get(warning_key, 0) + 1
    )

    warning_count = WARNINGS[warning_key]

    # First five violations
    if warning_count <= MAX_WARNINGS:

        try:
            await mute_user(
                client,
                chat_id,
                user_id
            )

        except Exception:
            LOGGER.exception("Mute failed")

        await send_warning(
            client,
            message,
            warning_count
        )

        return

    # Sixth violation: permanent ban
    try:

        await client.ban_chat_member(
            chat_id,
            user_id
        )

        await client.send_message(
            chat_id,
            (
                "🚫 𝐔𝐒𝐄𝐑 𝐁𝐀𝐍𝐍𝐄𝐃\n\n"
                f"👤 Member: {user.mention}\n"
                "⚠️ Reason: Repeated explicit media violations.\n"
                f"🔢 Total warnings: {warning_count}\n\n"
                "This member has been permanently banned."
            ),
            reply_markup=warning_buttons()
        )

        LOGGER.info(
            "User %s banned from chat %s",
            user_id,
            chat_id
        )

    except Exception:
        LOGGER.exception("Permanent ban failed")


# --------------------------------------------------
# REGISTER HANDLERS
# --------------------------------------------------

def register_moderation_handlers(app):

    # Rules command
    app.on_message(
        filters.command("rules") & filters.group
    )(rules_command)

    # Rules callback
    app.on_callback_query(
        filters.regex("^moderation_rules$")
    )(moderation_callback)

    # ONLY stickers and GIFs
    app.on_message(
        filters.group
        & (filters.sticker | filters.animation)
    )(moderation_filter)

    LOGGER.info(
        "NSFW sticker/GIF moderation registered successfully"
    )
