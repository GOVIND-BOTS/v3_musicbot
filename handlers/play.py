
import html
import logging
import re
from contextlib import suppress

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode

from buttons import stream_buttons
from .callbacks import start_progress_updater
from config import OWNER_ID, SUDO_USERS
from database.mongodb import get_chat_settings
from player_ui import add_requester, now_playing_caption
from owner_manager import get_owner_url
from thumbnails import get_thumb, save_requester_avatar
from youtube import (
    is_youtube_url,
    is_media_url,
    search_youtube,
    get_video_info,
    get_stream_url,
)

LOGGER = logging.getLogger(__name__)


def stylize(text):
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    styled = (
        "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁"
        "𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛"
    )
    return str(text).translate(str.maketrans(normal, styled))


def get_owner_ids():
    ids = set()

    if isinstance(OWNER_ID, (list, tuple, set)):
        ids.update(OWNER_ID)
    elif OWNER_ID:
        ids.add(OWNER_ID)

    if isinstance(SUDO_USERS, (list, tuple, set)):
        ids.update(SUDO_USERS)
    elif SUDO_USERS:
        ids.add(SUDO_USERS)

    result = set()

    for user_id in ids:
        try:
            result.add(int(user_id))
        except (TypeError, ValueError):
            continue

    return result


def get_video_id(track):
    video_id = (
        track.get("videoid")
        or track.get("video_id")
        or track.get("id")
    )

    if video_id and re.fullmatch(
        r"[A-Za-z0-9_-]{6,20}",
        str(video_id),
    ):
        return str(video_id)

    url = (
        track.get("webpage_url")
        or track.get("original_url")
        or track.get("url")
        or ""
    )

    patterns = (
        r"(?:youtube\.com/watch\?.*?v=)([A-Za-z0-9_-]{6,20})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{6,20})",
        r"(?:youtube\.com/(?:shorts|embed)/)([A-Za-z0-9_-]{6,20})",
    )

    for pattern in patterns:
        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return None


async def _get_requester_avatar(user_id, *clients):
    """Download the largest available Telegram profile photo from either client."""
    if not user_id:
        return None

    for photo_client in clients:
        if not photo_client:
            continue
        try:
            photos = await photo_client.get_user_profile_photos(
                int(user_id), limit=1
            )
            if not photos or not photos.photos:
                continue

            sizes = photos.photos[0]
            if not sizes:
                continue
            photo = max(sizes, key=lambda item: getattr(item, "file_size", 0) or 0)

            data = await photo_client.download_media(
                photo.file_id, in_memory=True
            )
            if data is None:
                continue
            if hasattr(data, "getvalue"):
                raw = data.getvalue()
            elif hasattr(data, "read"):
                data.seek(0)
                raw = data.read()
            elif isinstance(data, (bytes, bytearray)):
                raw = bytes(data)
            else:
                LOGGER.warning("Unexpected requester photo download result: %s",
                               type(data).__name__)
                continue

            if raw:
                LOGGER.info("Requester profile photo downloaded for user %s", user_id)
                return raw
        except Exception:
            LOGGER.debug(
                "Could not fetch requester profile photo using %s",
                type(photo_client).__name__,
                exc_info=True,
            )
    LOGGER.warning("No accessible profile photo found for requester %s", user_id)
    return None


async def generate_track_thumbnail(track, client=None, assistant=None):
    try:
        video_id = get_video_id(track)

        if not video_id:
            LOGGER.warning("YouTube video ID not found for thumbnail.")
            return track

        user_id = track.get("requested_by")
        if isinstance(user_id, dict):
            user_id = user_id.get("id")

        track["videoid"] = video_id
        avatar_data = await _get_requester_avatar(
            user_id, client, assistant
        )
        avatar_path = save_requester_avatar(avatar_data, user_id)
        if avatar_path:
            track["_requester_avatar_path"] = avatar_path

        requester = (
            track.get("requested_by_name")
            or track.get("requested_by_username")
            or "Group member"
        )

        thumbnail = await get_thumb(
            videoid=video_id,
            title=track.get("title", "Unknown Track"),
            duration=track.get("duration", "Unknown"),
            channel=track.get("channel", "YouTube"),
            bot_name="GOVIND MUSIC",
            requested_by=requester,
            requester_avatar=avatar_data,
        )

        if thumbnail:
            track["thumbnail"] = thumbnail
            LOGGER.info(
                "Custom thumbnail generated: video_id=%s avatar_loaded=%s path=%s",
                video_id, bool(avatar_data), thumbnail
            )

    except Exception:
        LOGGER.exception("Track thumbnail generation failed.")

    return track

async def is_chat_admin(client, chat_id, user_id):
    if user_id in get_owner_ids():
        return True

    try:
        member = await client.get_chat_member(chat_id, user_id)

        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )

    except Exception:
        return False


async def ensure_assistant_joined(client, assistant, chat_id):
    if not assistant:
        return False

    try:
        member = await assistant.get_chat_member(
            chat_id,
            assistant.me.id,
        )

        if member.status not in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.BANNED,
        ):
            return True

    except Exception:
        pass

    try:
        chat = await client.get_chat(chat_id)

        if chat.username:
            await assistant.join_chat(chat.username)

        else:
            invite = await client.create_chat_invite_link(
                chat_id,
                member_limit=1,
            )

            try:
                await assistant.join_chat(invite.invite_link)
            finally:
                with suppress(Exception):
                    await client.revoke_chat_invite_link(
                        chat_id,
                        invite.invite_link,
                    )

        return True

    except Exception as error:
        LOGGER.exception("Assistant join failed: %s", error)
        return False


async def send_player_card(client, chat_id, track, stream):
    caption = now_playing_caption(track)

    keyboard = stream_buttons(
        chat_id,
        elapsed=0,
        duration=track.get("duration", 0),
        owner_url=track.get("_owner_url"),
    )

    thumbnail = track.get("thumbnail")

    try:
        if thumbnail:
            message = await client.send_photo(
                chat_id,
                photo=thumbnail,
                caption=caption,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )
        else:
            message = await client.send_message(
                chat_id,
                text=caption,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )

    except Exception:
        LOGGER.exception("Player card photo failed; sending text card.")

        message = await client.send_message(
            chat_id,
            text=caption,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    stream.player_messages[chat_id] = message
    return message


async def resolve_track(query, media_type):
    if is_media_url(query):
        info = await get_video_info(query)

        if not info:
            return None

        track = dict(info)
        if media_type == "video" and track.get("has_video") is False:
            media_type = "audio"

    else:
        results = await search_youtube(query, limit=1)

        if not results:
            return None

        track = dict(results[0])

    webpage_url = (
        track.get("webpage_url")
        or track.get("original_url")
        or track.get("url")
        or query
    )

    stream_url = await get_stream_url(
        webpage_url,
        media_type,
    )

    if isinstance(stream_url, dict):
        track.update(stream_url)
    elif stream_url:
        track["url"] = stream_url

    if not track.get("url"):
        return None

    track["webpage_url"] = webpage_url
    track["media_type"] = media_type

    return track


def register_play_handlers(app, stream, assistant=None):

    async def handle_play(
        client,
        message,
        media_type="audio",
        query=None,
    ):
        if not message.from_user:
            return

        chat_id = message.chat.id

        try:
            settings = await get_chat_settings(chat_id) or {}
        except Exception:
            LOGGER.exception("Could not load chat settings for %s", chat_id)
            settings = {}

        clean_mode = settings.get("clean_mode", False)

        if clean_mode:
            with suppress(Exception):
                await message.delete()

        if query is None:
            query = message.text or message.caption or ""

            if message.text:
                query = re.sub(
                    r"^/\w+(?:@\w+)?\s*",
                    "",
                    query,
                ).strip()

        query = query.strip()

        if not query:
            usage = (
                f"{stylize('Usage:')}\n"
                "<code>/play song name</code> — "
                f"{stylize('Audio')}\n"
                "<code>/vplay song name</code> — "
                f"{stylize('Video')}"
            )

            await message.reply_text(
                usage,
                parse_mode=ParseMode.HTML,
            )
            return

        status = None

        if not clean_mode:
            status = await client.send_message(
                chat_id,
                stylize("Searching for your requested track..."),
            )

        try:
            track = await resolve_track(query, media_type)

            if not track:
                error_text = stylize("No playable track found.")

                if status:
                    await status.edit_text(error_text)
                else:
                    await client.send_message(chat_id, error_text)

                return

            if assistant:
                joined = await ensure_assistant_joined(
                    client,
                    assistant,
                    chat_id,
                )

                if not joined:
                    error_text = stylize(
                        "Assistant account could not join this chat. "
                        "Please add the assistant to the group."
                    )

                    if status:
                        await status.edit_text(error_text)
                    else:
                        await client.send_message(chat_id, error_text)

                    return

            track = add_requester(track, message.from_user)
            track["_owner_url"] = await get_owner_url()
            track = await generate_track_thumbnail(track, client, assistant)

            result = await stream.play(
                chat_id,
                track,
                media_type=media_type,
            )

            if result == "queued":
                if status:
                    await status.edit_text(
                        stylize("Track added to the queue.")
                    )
                else:
                    await client.send_message(
                        chat_id,
                        stylize("Track added to the queue."),
                    )
                return

            if result != "playing":
                error_text = stylize("Unable to start playback.")

                if status:
                    await status.edit_text(error_text)
                else:
                    await client.send_message(chat_id, error_text)

                return

            if status:
                with suppress(Exception):
                    await status.delete()

            await send_player_card(
                client,
                chat_id,
                track,
                stream,
            )

            start_progress_updater(
                client,
                chat_id,
                track,
                stream,
            )

        except Exception as error:
            LOGGER.exception("Play handler error")

            error_text = (
                f"{stylize('Playback error:')}\n"
                f"<code>{html.escape(str(error))[:500]}</code>"
            )

            if status:
                with suppress(Exception):
                    await status.edit_text(
                        error_text,
                        parse_mode=ParseMode.HTML,
                    )
            else:
                await client.send_message(
                    chat_id,
                    error_text,
                    parse_mode=ParseMode.HTML,
                )

    @app.on_message(filters.command("play") & filters.group)
    async def audio_play(client, message):
        await handle_play(client, message, "audio")

    @app.on_message(filters.command("vplay") & filters.group)
    async def video_play(client, message):
        await handle_play(client, message, "video")

    alias_pattern = (
        r"^(?:(?:adisha|babu|baby)\s+(?:play|vplay)"
        r"|(?:play|vplay)\s+(?:adisha|babu|baby))\b"
    )

    @app.on_message(
        filters.text
        & filters.group
        & filters.regex(alias_pattern, flags=re.IGNORECASE)
    )
    async def play_alias(client, message):
        text = message.text or ""

        match = re.match(
            r"^(?:(?:adisha|babu|baby)\s+)?(play|vplay)\b"
            r"|^(play|vplay)\s+(?:adisha|babu|baby)\b",
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return

        command = (match.group(1) or match.group(2)).lower()

        query = re.sub(
            r"^(?:(?:adisha|babu|baby)\s+)?(?:play|vplay)\b\s*"
            r"|^(?:play|vplay)\s+(?:adisha|babu|baby)\b\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        if not query:
            await message.reply_text(
                stylize("Please provide a song name or YouTube link.")
            )
            return

        await handle_play(
            client,
            message,
            "video" if command == "vplay" else "audio",
            query=query,
        )

    @app.on_message(filters.command("joinuserbot") & filters.group)
    async def join_userbot(client, message):
        if not message.from_user:
            return

        if not await is_chat_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return

        if not assistant:
            await message.reply_text(
                stylize("Assistant client is not configured.")
            )
            return

        joined = await ensure_assistant_joined(
            client,
            assistant,
            message.chat.id,
        )

        text = (
            stylize("Assistant joined successfully.")
            if joined
            else stylize("Assistant could not join this chat.")
        )

        await message.reply_text(text)

    LOGGER.info("Play handlers registered")
