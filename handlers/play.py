
import html
import logging
import re
from contextlib import suppress

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from buttons import stream_buttons
from config import OWNER_ID, SUDO_USERS
from database.mongodb import get_chat_settings
from player_ui import add_requester, now_playing_caption
from youtube import (
    is_youtube_url,
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

    return ids


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


async def can_play(client, message, settings):
    user = message.from_user
    if not user:
        return False

    if user.id in get_owner_ids():
        return True

    if await is_chat_admin(client, message.chat.id, user.id):
        return True

    authorized_users = settings.get("authorized_users", [])
    return user.id in authorized_users


async def ensure_assistant_joined(client, assistant, chat_id):
    try:
        member = await assistant.get_chat_member(chat_id, assistant.me.id)

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

    keyboard = stream_buttons(chat_id)

    try:
        message = await client.send_photo(
            chat_id,
            photo=track.get("thumbnail"),
            caption=caption,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        message = await client.send_message(
            chat_id,
            caption,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    stream.player_messages[chat_id] = message
    return message


async def resolve_track(query, media_type):
    if is_youtube_url(query):
        info = await get_video_info(query)

        if not info:
            return None

        track = dict(info)
    else:
        results = await search_youtube(query, limit=1)

        if not results:
            return None

        track = dict(results[0])

    webpage_url = (
        track.get("webpage_url")
        or track.get("url")
        or query
    )

    stream_url = await get_stream_url(webpage_url, media_type)

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

    async def handle_play(client, message, media_type="audio"):
        if not message.from_user:
            return

        chat_id = message.chat.id

        try:
            settings = await get_chat_settings(chat_id)
        except Exception:
            settings = {}

        clean_mode = settings.get("clean_mode", False)

        if not await can_play(client, message, settings):
            if clean_mode:
                with suppress(Exception):
                    await message.delete()

            await message.reply_text(
                stylize("Only admins and authorized users can play music."),
                parse_mode=ParseMode.HTML,
            )
            return

        query = message.text or message.caption or ""

        if message.text:
            query = re.sub(r"^/\w+(?:@\w+)?\s*", "", query).strip()

        if not query:
            if clean_mode:
                with suppress(Exception):
                    await message.delete()

            usage = (
                f"{stylize('Usage:')}\n"
                f"<code>/play song name</code> — {stylize('Audio')}\n"
                f"<code>/vplay song name</code> — {stylize('Video')}"
            )

            await message.reply_text(
                usage,
                parse_mode=ParseMode.HTML,
            )
            return

        if clean_mode:
            with suppress(Exception):
                await message.delete()

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

            add_requester(track, message.from_user)

            started = await stream.play(chat_id, track)

            if not started:
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

            if status:
                with suppress(Exception):
                    await status.delete()

            await send_player_card(
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

    aliases = (
        r"^(?:adisha|babu|baby)\s+(?:play|vplay)"
        r"|^(?:play|vplay)\s+(?:adisha|babu|baby)"
    )

    @app.on_message(
        filters.text
        & filters.group
        & filters.regex(aliases, flags=re.IGNORECASE)
    )
    async def play_alias(client, message):
        text = message.text or ""
        match = re.match(
            r"^(?:(?:adisha|babu|baby)\s+)?(play|vplay)"
            r"|^(play|vplay)\s+(?:adisha|babu|baby)",
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return

        command = (match.group(1) or match.group(2)).lower()

        query = re.sub(
            r"^(?:(?:adisha|babu|baby)\s+)?(?:play|vplay)\s*"
            r"|^(?:play|vplay)\s+(?:adisha|babu|baby)\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        if not query:
            return

        message.text = f"/{command} {query}"
        await handle_play(
            client,
            message,
            "video" if command == "vplay" else "audio",
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
            return await message.reply_text(
                stylize("Assistant client is not configured.")
            )

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
