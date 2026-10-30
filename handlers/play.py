
import logging
from contextlib import suppress

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode

from buttons import stream_buttons
from player_ui import add_requester, now_playing_caption
from thumbnails import get_thumb
from youtube import (
    is_youtube_url,
    search_youtube,
    get_video_info,
    get_stream_url,
)

LOGGER = logging.getLogger(__name__)


async def ensure_assistant_joined(bot, assistant, chat_id):
    """Ensure assistant account is a member of the target group."""

    if assistant is None:
        raise RuntimeError("Assistant client is not available.")

    me = await assistant.get_me()

    try:
        member = await assistant.get_chat_member(chat_id, me.id)

        if member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
        ):
            return True

        if (
            member.status == ChatMemberStatus.RESTRICTED
            and getattr(member, "is_member", False)
        ):
            return True

    except Exception:
        LOGGER.info(
            "Assistant is not a member of group %s",
            chat_id,
        )

    invite_link = None

    try:
        chat = await bot.get_chat(chat_id)

        # Try joining a public group directly.
        if chat.username:
            try:
                await assistant.join_chat(chat.username)
                LOGGER.info(
                    "Assistant joined public group %s",
                    chat_id,
                )
                return True
            except Exception:
                LOGGER.warning(
                    "Direct public group join failed.",
                    exc_info=True,
                )

        # For private groups, create a temporary invite link.
        invite = await bot.create_chat_invite_link(
            chat_id,
            member_limit=1,
        )
        invite_link = invite.invite_link

        await assistant.join_chat(invite_link)

        LOGGER.info(
            "Assistant joined group %s",
            chat_id,
        )
        return True

    except Exception as exc:
        LOGGER.exception(
            "Assistant could not join group %s",
            chat_id,
        )
        raise RuntimeError(
            "Assistant could not join this group. "
            "Give the bot permission to invite users, "
            "and check the Assistant account restrictions."
        ) from exc

    finally:
        if invite_link:
            with suppress(Exception):
                await bot.revoke_chat_invite_link(
                    chat_id,
                    invite_link,
                )


def register_play_handlers(app, stream, assistant=None):

    async def handle_play(
        client,
        message,
        force_video=False,
        query_text=None,
    ):
        if not query_text:
            if len(message.command) < 2:
                await message.reply_text(
                    "Usage:\n\n"
                    "play song name - Audio\n"
                    "vplay song name - Video\n\n"
                    "/play song name\n"
                    "/vplay song name\n\n"
                    "adisha play song name\n"
                    "adisha vplay song name\n"
                    "babu play song name\n"
                    "baby play song name"
                )
                return

            query_text = " ".join(
                message.command[1:]
            ).strip()

        if not query_text:
            await message.reply_text(
                "❌ Please enter a song name."
            )
            return

        status = await message.reply_text(
            "🔎 Searching and preparing your song..."
        )

        try:
            # Resolve YouTube URL or first search result.
            if is_youtube_url(query_text):
                track = await get_video_info(query_text)
            else:
                results = await search_youtube(
                    query_text,
                    limit=1,
                )

                results = [
                    item
                    for item in results
                    if item and item.get("webpage_url")
                ]

                if not results:
                    await status.edit_text(
                        "❌ No results found. Try another song."
                    )
                    return

                track = results[0]

            if not track or not track.get("webpage_url"):
                await status.edit_text(
                    "❌ Unable to find a playable song."
                )
                return

            # PLAY = AUDIO ONLY
            # VPLAY = VIDEO ONLY
            media_type = (
                "video" if force_video else "audio"
            )

            await status.edit_text(
                f"⏳ Preparing {media_type} stream..."
            )

            playable = await get_stream_url(
                track["webpage_url"],
                media_type,
            )

            if not playable:
                await status.edit_text(
                    f"❌ Could not resolve the {media_type} stream."
                )
                return

            # Ensure assistant is in the group.
            await status.edit_text(
                "👤 Checking Assistant membership..."
            )

            await ensure_assistant_joined(
                client,
                assistant,
                message.chat.id,
            )

            # Save requester details.
            if message.from_user:
                playable = add_requester(
                    playable,
                    message.from_user,
                )
            else:
                playable = dict(playable)
                playable.setdefault("requested_by_id", 0)
                playable.setdefault(
                    "requested_by_name",
                    "Group member",
                )
                playable.setdefault(
                    "requested_by_username",
                    "",
                )

            # Start playback or add to queue.
            result = await stream.play(
                message.chat.id,
                playable,
                media_type,
            )

            if result == "queued":
                await status.edit_text(
                    "➕ **Added to Queue**\n\n"
                    f"🎵 **{playable.get('title', 'Unknown')}**\n"
                    f"🎧 Type: {media_type.title()}\n"
                    f"👤 Requested by: "
                    f"{playable.get('requested_by_name', 'Group member')}"
                )
                return

            # Generate thumbnail.
            thumb = await get_thumb(
                playable.get("videoid"),
                playable.get("title"),
                playable.get("duration_text")
                or playable.get("duration"),
                playable.get("views", 0),
                playable.get("channel", "YouTube"),
                "GOVIND MUSIC",
                playable.get(
                    "requested_by_name",
                    "Group member",
                ),
            )

            caption = now_playing_caption(playable)

            await status.delete()

            if thumb:
                await client.send_photo(
                    chat_id=message.chat.id,
                    photo=thumb,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=stream_buttons(
                        message.chat.id
                    ),
                )
            else:
                await client.send_message(
                    chat_id=message.chat.id,
                    text=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=stream_buttons(
                        message.chat.id
                    ),
                )

        except Exception as exc:
            LOGGER.exception(
                "Unable to start playback"
            )

            error_message = (
                "❌ Unable to play this song.\n\n"
                f"Error: `{type(exc).__name__}`\n\n"
                f"{str(exc)[:500]}"
            )

            with suppress(Exception):
                await status.edit_text(error_message)

    # Manual Assistant join command.
    async def handle_joinuserbot(client, message):
        status = await message.reply_text(
            "👤 Checking Assistant membership..."
        )

        try:
            await ensure_assistant_joined(
                client,
                assistant,
                message.chat.id,
            )

            await status.edit_text(
                "✅ Assistant successfully joined "
                "or is already in this group!"
            )

        except Exception as exc:
            LOGGER.exception(
                "Manual Assistant join failed"
            )

            await status.edit_text(
                "❌ Assistant could not join this group.\n\n"
                f"Error: `{type(exc).__name__}`\n"
                f"{str(exc)[:400]}"
            )

    # /play = AUDIO ONLY
    @app.on_message(
        filters.command("play") & filters.group
    )
    async def play_command(client, message):
        await handle_play(
            client,
            message,
            force_video=False,
        )

    # /vplay = VIDEO ONLY
    @app.on_message(
        filters.command("vplay") & filters.group
    )
    async def vplay_command(client, message):
        await handle_play(
            client,
            message,
            force_video=True,
        )
(
        filters.command("joinuserbot") & filters.group
    )
    async def joinuserbot_command(client, message):
        await handle_joinuserbot(client, message)


    @app.on_message(
        filters.regex(
            r"(?i)^(?:(?:adisha|babu|baby)\s+)?"
            r"(play|vplay)\s+(.+)$"
        )
        & filters.group
        & filters.text
    )
    async def plain_play_command(client, message):
        match = (
            message.matches[0]
            if message.matches
            else None
        )

        if not match:
            return

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
