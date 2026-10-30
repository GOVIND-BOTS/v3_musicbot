
import logging

from pyrogram import filters
from pyrogram.enums import ParseMode

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


def register_play_handlers(app, stream):

    async def handle_play(
        client,
        message,
        force_video=False,
        query_text=None,
    ):
        if not query_text:
            if len(message.command) < 2:
                await message.reply_text(
                    "Usage:\n"
                    "/play song name\n"
                    "/vplay song name\n\n"
                    "Or:\n"
                    "adisha play song name\n"
                    "baby play song name"
                )
                return

            query_text = " ".join(message.command[1:]).strip()

        status = await message.reply_text(
            "🔎 Searching and preparing your song..."
        )

        try:
            # YouTube URL or first search result.
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

            media_type = "video" if force_video else "audio"

            await status.edit_text(
                f"⏳ Starting {media_type} playback..."
            )

            playable = await get_stream_url(
                track["webpage_url"],
                media_type,
            )

            if not playable:
                await status.edit_text(
                    "❌ Could not resolve the audio stream."
                )
                return

            # Save requester details with the track.
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
                    f"👤 Requested by: "
                    f"{playable.get('requested_by_name', 'Group member')}"
                )
                return

            # Generate player thumbnail.
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
            LOGGER.exception("Unable to start playback")

            error_message = (
                "❌ Unable to play this song.\n\n"
                f"Error: `{type(exc).__name__}`\n\n"
                "Check YouTube cookies and stream logs."
            )

            try:
                await status.edit_text(error_message)
            except Exception:
                LOGGER.warning(
                    "Could not update playback status message."
                )

    # Normal /play command.
    @app.on_message(
        filters.command("play") & filters.group
    )
    async def play_command(client, message):
        await handle_play(
            client,
            message,
            force_video=False,
        )

    # Normal /vplay command.
    @app.on_message(
        filters.command("vplay") & filters.group
    )
    async def vplay_command(client, message):
        await handle_play(
            client,
            message,
            force_video=True,
        )

    # adisha play / adisha vplay
    # baby play / baby vplay
    @app.on_message(
        filters.regex(
            r"(?i)^(?:adisha|baby)\s+(play|vplay)\s+(.+)$"
        )
        & filters.group
    )
    async def custom_play_command(client, message):
        match = (
            message.matches[0]
            if message.matches
            else None
        )

        if not match:
            return

        command = match.group(1).lower()
        query = match.group(2).strip()

        await handle_play(
            client,
            message,
            force_video=(command == "vplay"),
            query_text=query,
        )
