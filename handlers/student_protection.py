
import asyncio
import logging
import os
import re
import tempfile
import threading

from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2

from nudenet import NudeDetector
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
# CONFIGURATION
# --------------------------------------------------

MAX_WARNINGS = 7
MUTE_MINUTES = 10

MAX_MEDIA_SIZE = 20 * 1024 * 1024
MAX_VIDEO_FRAMES = 8
VIDEO_FRAME_INTERVAL_MS = 1000

# Conservative confidence threshold.
MEDIA_CONFIDENCE = 0.82

# Only high-confidence exposed-content categories
# are treated as violations.
EXPLICIT_LABELS = {
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
    "BUTTOCKS_EXPOSED",
}

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
• 7 warnings: Group ban.

<b>Stay respectful. Keep this group safe.</b>
"""


# --------------------------------------------------
# DETECTOR
# --------------------------------------------------

_detector = None
_detector_lock = threading.Lock()


def get_detector():
    global _detector

    if _detector is None:
        with _detector_lock:
            if _detector is None:
                LOGGER.info("Loading NudeNet media detector...")
                _detector = NudeDetector()
                LOGGER.info("NudeNet detector loaded.")

    return _detector


def detect_image_sync(image_path: str) -> bool:
    """
    Run NudeNet on one image.
    Returns True only for high-confidence detections.
    """

    detector = get_detector()

    detections = detector.detect(
        image_path,
        score_threshold=0.25,
    )

    for item in detections:
        label = item.get("class", "")
        score = float(item.get("score", 0))

        if (
            label in EXPLICIT_LABELS
            and score >= MEDIA_CONFIDENCE
        ):
            LOGGER.info(
                "Media classifier detected a restricted category "
                "with confidence %.2f",
                score,
            )
            return True

    return False


def detect_video_sync(video_path: str) -> bool:
    """
    Sample a limited number of video frames.
    Each sampled frame is checked independently.
    """

    capture = cv2.VideoCapture(video_path)

    if not capture.isOpened():
        LOGGER.warning("Could not open media file for frame analysis.")
        return False

    try:
        total_frames = int(
            capture.get(cv2.CAP_PROP_FRAME_COUNT)
        )

        fps = capture.get(cv2.CAP_PROP_FPS)

        if total_frames <= 0:
            return False

        if not fps or fps <= 0:
            fps = 25

        duration_ms = (total_frames / fps) * 1000

        detector = get_detector()

        with tempfile.TemporaryDirectory() as frame_dir:
            frame_number = 0
            position_ms = 0

            while (
                position_ms < duration_ms
                and frame_number < MAX_VIDEO_FRAMES
            ):
                capture.set(
                    cv2.CAP_PROP_POS_MSEC,
                    position_ms,
                )

                success, frame = capture.read()

                if not success:
                    break

                frame_path = os.path.join(
                    frame_dir,
                    f"frame_{frame_number}.jpg",
                )

                saved = cv2.imwrite(
                    frame_path,
                    frame,
                )

                if saved:
                    detections = detector.detect(
                        frame_path,
                        score_threshold=0.25,
                    )

                    for item in detections:
                        label = item.get("class", "")
                        score = float(item.get("score", 0))

                        if (
                            label in EXPLICIT_LABELS
                            and score >= MEDIA_CONFIDENCE
                        ):
                            LOGGER.info(
                                "Restricted media category "
                                "detected in sampled video frame."
                            )
                            return True

                frame_number += 1
                position_ms += VIDEO_FRAME_INTERVAL_MS

        return False

    finally:
        capture.release()


# --------------------------------------------------
# PRIVILEGED USERS
# --------------------------------------------------

def get_privileged_users():
    users = set()

    if isinstance(OWNER_ID, int):
        users.add(OWNER_ID)

    elif isinstance(OWNER_ID, (list, tuple, set)):
        users.update(
            user_id
            for user_id in OWNER_ID
            if isinstance(user_id, int)
        )

    if isinstance(SUDO_USERS, int):
        users.add(SUDO_USERS)

    elif isinstance(SUDO_USERS, (list, tuple, set)):
        users.update(
            user_id
            for user_id in SUDO_USERS
            if isinstance(user_id, int)
        )

    return users


PRIVILEGED_USERS = get_privileged_users()


# --------------------------------------------------
# TEXT NORMALIZATION
# --------------------------------------------------

def normalize_text(text: str) -> str:
    text = text.casefold()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_abuse(text: str) -> bool:
    if not text:
        return False

    normalized = normalize_text(text)

    if not normalized:
        return False

    words = set(normalized.split())

    for blocked in BLOCKED_WORDS:
        blocked = normalize_text(blocked)

        if not blocked:
            continue

        if " " in blocked:
            if blocked in normalized:
                return True

        elif blocked in words:
            return True

    return False


# --------------------------------------------------
# ADMIN CHECK
# --------------------------------------------------

async def is_exempt_user(client, chat_id: int, user_id: int):
    if user_id in PRIVILEGED_USERS:
        return True

    try:
        member = await client.get_chat_member(
            chat_id,
            user_id,
        )

        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )

    except Exception:
        LOGGER.exception(
            "Could not verify member privileges. "
            "Skipping moderation for safety."
        )
        return True


# --------------------------------------------------
# DELETE MESSAGE
# --------------------------------------------------

async def delete_violation(message):
    try:
        await message.delete()
        return True

    except Exception:
        LOGGER.exception("Could not delete violating message.")
        return False


# --------------------------------------------------
# MUTE
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

    except Exception:
        LOGGER.exception(
            "Could not mute user %s in chat %s.",
            user_id,
            chat_id,
        )
        return False


# --------------------------------------------------
# BAN
# --------------------------------------------------

async def ban_user(client, chat_id: int, user_id: int):
    try:
        await client.ban_chat_member(
            chat_id=chat_id,
            user_id=user_id,
        )
        return True

    except Exception:
        LOGGER.exception(
            "Could not ban user %s in chat %s.",
            user_id,
            chat_id,
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

    if message.from_user.is_bot:
        return

    if await is_exempt_user(
        client,
        chat_id,
        user_id,
    ):
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
        LOGGER.exception(
            "Could not save moderation warning."
        )
        return

    user_mention = message.from_user.mention

    if warnings >= MAX_WARNINGS:
        banned = await ban_user(
            client,
            chat_id,
            user_id,
        )

        if banned:
            response = (
                "🚫 <b>USER BANNED</b>\n\n"
                f"👤 User: {user_mention}\n"
                f"⚠️ Warnings: {warnings}/{MAX_WARNINGS}\n"
                f"📝 Reason: {reason}\n\n"
                "<b>Repeated group rule violations.</b>"
            )
        else:
            response = (
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

        mute_status = (
            f"🔇 Muted for {MUTE_MINUTES} minutes."
            if muted
            else "⚠️ Mute failed. Check bot permissions."
        )

        response = (
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
            response,
            disable_web_page_preview=True,
        )

    except Exception:
        LOGGER.exception(
            "Could not send moderation notification."
        )


# --------------------------------------------------
# TEXT MODERATION
# --------------------------------------------------

async def moderate_text(client, message):
    if not message.from_user:
        return

    text = message.text or ""

    if contains_abuse(text):
        await process_violation(
            client,
            message,
            "Abusive language",
        )


# --------------------------------------------------
# MEDIA FILE HELPERS
# --------------------------------------------------

def get_media_info(message):
    """
    Returns (extension, is_video, should_skip).
    """

    if message.photo:
        return ".jpg", False, False

    if message.sticker:
        sticker = message.sticker

        # TGS is an animated Lottie format.
        # It needs a separate renderer.
        if sticker.is_animated:
            return ".tgs", False, True

        if sticker.is_video:
            return ".webm", True, False

        return ".webp", False, False

    if message.animation:
        return ".mp4", True, False

    if message.video:
        return ".mp4", True, False

    if message.document:
        filename = message.document.file_name or ""
        extension = Path(filename).suffix.lower()

        supported_images = {
            ".jpg", ".jpeg", ".png", ".webp",
        }

        supported_videos = {
            ".gif", ".mp4", ".webm", ".mkv",
        }

        if extension in supported_images:
            return extension, False, False

        if extension in supported_videos:
            return extension, True, False

    return None, False, True


# --------------------------------------------------
# MEDIA MODERATION
# --------------------------------------------------

async def moderate_media(client, message):
    if not message.from_user:
        return

    if message.from_user.is_bot:
        return

    # Captions are checked here so media messages
    # are not processed twice by the text handler.
    caption = message.caption or ""

    if contains_abuse(caption):
        await process_violation(
            client,
            message,
            "Abusive media caption",
        )
        return

    extension, is_video, should_skip = get_media_info(
        message
    )

    if should_skip or not extension:
        return

    if await is_exempt_user(
        client,
        message.chat.id,
        message.from_user.id,
    ):
        return

    media = (
        message.photo
        or message.sticker
        or message.animation
        or message.video
        or message.document
    )

    if not media:
        return

    file_size = getattr(media, "file_size", None)

    if file_size and file_size > MAX_MEDIA_SIZE:
        LOGGER.info(
            "Skipping large media file in chat %s.",
            message.chat.id,
        )
        return

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            media_path = os.path.join(
                temp_dir,
                "incoming_media" + extension,
            )

            downloaded = await client.download_media(
                message,
                file_name=media_path,
            )

            if not downloaded or not os.path.isfile(downloaded):
                LOGGER.warning(
                    "Media download failed in chat %s.",
                    message.chat.id,
                )
                return

            actual_size = os.path.getsize(downloaded)

            if actual_size > MAX_MEDIA_SIZE:
                LOGGER.info("Downloaded media exceeds size limit.")
                return

            if is_video:
                flagged = await asyncio.to_thread(
                    detect_video_sync,
                    downloaded,
                )
            else:
                flagged = await asyncio.to_thread(
                    detect_image_sync,
                    downloaded,
                )

            if flagged:
                await process_violation(
                    client,
                    message,
                    "Inappropriate media detected",
                )

    except Exception:
        # Fail open: never punish a member if the
        # classifier or download process fails.
        LOGGER.exception(
            "Media moderation failed in chat %s. "
            "Message was not automatically punished.",
            message.chat.id,
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
# WARNINGS COMMAND
# --------------------------------------------------

async def warnings_command(client, message):
    if not message.from_user:
        return

    target = (
        message.reply_to_message.from_user
        if message.reply_to_message
        else message.from_user
    )

    if not target:
        return

    if target.id != message.from_user.id:
        if not await is_exempt_user(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            await message.reply_text(
                "❌ Only group admins can check "
                "another member's warnings."
            )
            return

    try:
        data = await get_moderation_data(
            message.chat.id,
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
    # Text-only messages
    app.on_message(
        filters.group
        & filters.text
        & ~filters.command(
            ["rules", "warns", "resetwarns"]
        )
    )(moderate_text)

    # Photos, stickers, GIFs, videos and supported documents
    app.on_message(
        filters.group
        & (
            filters.photo
            | filters.sticker
            | filters.animation
            | filters.video
            | filters.document
        )
    )(moderate_media)

    # Rules
    app.on_message(
        filters.group
        & filters.command("rules")
    )(rules_command)

    # Warning count
    app.on_message(
        filters.group
        & filters.command("warns")
    )(warnings_command)

    # Reset warnings
    app.on_message(
        filters.group
        & filters.command("resetwarns")
    )(reset_warnings_command)

    LOGGER.info(
        "Student Protection System registered "
        "(text + supported media)."
    )
