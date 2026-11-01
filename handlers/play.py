
import logging
from contextlib import suppress

from pyrogram import filters
from pyrogram.enums import ParseMode

from buttons import stream_buttons
from player_ui import add_requester, now_playing_caption
from thumbnails import get_thumb
from youtube import (
    is_youtube_url,
    search_youtube,
    get_stream_url,
)

LOGGER = logging.getLogger(__name__)


async def ensure_assistant_joined(bot, assistant, chat_id):
    """Ensure the Assistant account is present in the group."""

    if assistant is None:
        raise RuntimeError("Assistant client is not available.")

    me = await assistant.get_me()

    try:
        member = await assistant.get_chat_member(chat_id, me.id)
        status = str(member.status).lower().split(".")[-1]

        if status in ("owner", "administrator", "member"):
            return True

        if status == "restricted" and getattr(member, "is_member", False):
            return True

    except Exception:
        LOGGER.info(
            "Assistant is not currently in group %s.",
            chat_id,
        )

    invite_link = None

    try:
        chat = await bot.get_chat(chat_id)

        if chat.username:
            try:
                await assistant.join_chat(chat.username)
                return True
            except Exception:
                LOGGER.warning(
                    "Public group join failed.",
                    exc_info=True,
                )

        invite = await bot.create_chat_invite_link(
            chat_id,
            member_limit=1,
        )
        invite_link = invite.invite_link

        await assistant.join_chat(invite_link)
        return True

    except Exception as exc:
        LOGGER.exception(
            "Assistant could not join group %s.",
            chat_id,
        )

        raise RuntimeError(
            "Assistant could not join this group. "
            "Check the Assistant account and bot permissions."
        ) from exc

    finally:
        if invite_link:
            with suppress(Exception):
                await bot.revoke_chat_invite_link(
                    chat_id,
                    invite_link,
                )


async def send_player_card(client, chat_id, track, stream):
    """Send the Now Playing card and save its message."""

    thumb = await get_thumb(
        track.get("videoid"),
        track.get("title"),
        track.get("duration_text") or track.get("duration"),
        track.get("views", 0),
        track.get("channel", "YouTube"),
        "GOVIND MUSIC",
        track.get("requested_by_name", "Group member"),
    )

    caption = now_playing_caption(track)
    keyboard = stream_buttons(chat_id)

    if thumb:
        sent = await client.send_photo(
            chat_id=chat_id,
            photo=thumb,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
    else:
        sent = await client.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )

    stream.player_messages[chat_id] = sent
    return sent


def register_play_handlers(app, stream, assistant=None):

    async def handle_play(
        client,
        message,
        force_video=False,
        query_text=None,
    ):
        # Read query before deleting the command message.
        if not query_text:
            if not message.command or len(message.command) < 2:
                with suppress(Exception):
                    await message.delete()
                await client.send_message(
                    message.chat.id,
                    "🎵 <b>GOVIND MUSIC</b>\n\n"
                    "Usage:\n"
                    "<code>/play song name</code> - Audio\n"
                    "<code>/vplay song name</code> - Video\n"
                    "<code>play babu song name</code>\n"
                    "<code>play baby song name</code>\n"
                    "<code>adisha play song name</code>",
                    parse_mode=ParseMode.HTML,
                )
                return

            query_text = " ".join(message.command[1:]).strip()

        query_text = (query_text or "").strip()

        if not query_text:
            with suppress(Exception):
                await message.delete()

            await client.send_message(
                message.chat.id,
                "❌ Please enter a song name.",
            )
            return

        # Delete the user's command message first.
        with suppress(Exception):
            await message.delete()

        # Send the bot response after attempting deletion.
        status = await client.send_message(
            message.chat.id,
            "🔎 Searching for your song...",
        )

        try:
            # Resolve YouTube URL or search for a song.
            if is_youtube_url(query_text):
                video_url = query_text
            else:
                results = await search_youtube(
                    query_text,
                    limit=1,
                )

                results = [
                    item for item in results
                    if item and item.get("webpage_url")
                ]

                if not results:
                    await status.edit_text(
                        "❌ No results found. Try another song."
                    )
                    return

                video_url = results[0]["webpage_url"]

            media_type = "video" if force_video else "audio"

            await status.edit_text(
                f"⏳ Preparing {media_type} stream..."
            )

            playable = await get_stream_url(
                video_url,
                media_type,
            )

            if not playable or not playable.get("url"):
                await status.edit_text(
                    "❌ Could not resolve a playable stream."
                )
                return

            await status.edit_text(
                "👤 Checking Assistant membership..."
            )

            await ensure_assistant_joined(
                client,
                assistant,
                message.chat.id,
            )

            playable = add_requester(
                playable,
                message.from_user,
            )

            result = await stream.play(
                message.chat.id,
                playable,
                media_type,
            )

            if result == "queued":
                await status.edit_text(
                    "➕ <b>Added to Queue</b>\n\n"
                    f"🎵 <b>{playable.get('title', 'Unknown')}</b>\n"
                    f"🎧 Type: {media_type.title()}\n"
                    "👤 Requested by: "
                    f"{playable.get('requested_by_name', 'Group member')}",
                    parse_mode=ParseMode.HTML,
                )
                return

            # First track started successfully.
            with suppress(Exception):
                await status.delete()

            await send_player_card(
                client,
                message.chat.id,
                playable,
                stream,
            )

            LOGGER.info(
                "%s playback started in %s: %s",
                media_type.upper(),
                message.chat.id,
                playable.get("title", "Unknown"),
            )

        except Exception as exc:
            LOGGER.exception("Unable to start playback.")

            error_message = (
                "❌ <b>Unable to play this song.</b>\n\n"
                f"Error: <code>{type(exc).__name__}</code>\n"
                f"<code>{str(exc)[:500]}</code>"
            )

            with suppress(Exception):
                await status.edit_text(
                    error_message,
                    parse_mode=ParseMode.HTML,
                )

    async def handle_joinuserbot(client, message):
        with suppress(Exception):
            await message.delete()

        status = await client.send_message(
            message.chat.id,
            "👤 Checking Assistant membership...",
        )

        try:
            await ensure_assistant_joined(
                client,
                assistant,
                message.chat.id,
            )

            await status.edit_text(
                "✅ Assistant is already in the group or joined successfully."
            )

        except Exception as exc:
            LOGGER.exception("Manual Assistant join failed.")

            await status.edit_text(
                "❌ Assistant could not join the group.\n\n"
                f"Error: <code>{type(exc).__name__}</code>\n"
                f"<code>{str(exc)[:400]}</code>",
                parse_mode=ParseMode.HTML,
            )

    # /play = AUDIO
    @app.on_message(
        filters.command("play") & filters.group
    )
    async def play_command(client, message):
        await handle_play(
            client,
            message,
            force_video=False,
        )

    # /vplay = VIDEO
    @app.on_message(
        filters.command("vplay") & filters.group
    )
    async def vplay_command(client, message):
        await handle_play(
            client,
            message,
            force_video=True,
        )

    # /joinuserbot
    @app.on_message(
        filters.command("joinuserbot") & filters.group
    )
    async def joinuserbot_command(client, message):
        await handle_joinuserbot(client, message)

    # Plain text aliases:
    # play babu, play baby, adisha play, babu play, baby play.
    @app.on_message(
        filters.regex(
            r"(?i)^(?:(?:adisha|babu|baby)\s+)?"
            r"(play|vplay)\s+(.+)$"
        )
        & filters.group
        & filters.text
    )
    async def plain_play_command(client, message):
        if not message.matches:
            return

        match = message.matches[0]
        command = match.group(1).lower()
        query = match.group(2).strip()

        if not query:
            return

        await handle_play(
            client,
            message,
            force_video=(command == "vplay"),
            query_text=query,
        )
