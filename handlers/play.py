
import logging

from pyrogram import filters

from buttons import stream_buttons
from config import BOT_NAME, TRIGGER
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
                    "`/play song name`\n"
                    "`/vplay song name`"
                )
                return

            query_text = " ".join(message.command[1:]).strip()

        status = await message.reply_text(
            "🔎 Searching and preparing your song..."
        )

        try:
            # Direct YouTube URL or first search result.
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

                # Automatically use the first result.
                track = results[0]

            media_type = "video" if force_video else "audio"

            await status.edit_text(
                f"⏳ Starting {media_type} playback..."
            )

            # Resolve the actual stream URL.
            playable = await get_stream_url(
                track["webpage_url"],
                media_type,
            )

            # Play in VC or add to the existing queue.
            result = await stream.play(
                message.chat.id,
                playable,
                media_type,
            )

            if result == "queued":
                await status.edit_text(
                    f"➕ Added to queue:\n"
                    f"**{playable['title']}**"
                )
                return

            thumb = await get_thumb(
                playable.get("videoid"),
                playable.get("title"),
                playable.get("duration_text"),
                playable.get("views"),
                playable.get("channel"),
                BOT_NAME,
            )

            await status.delete()

            await client.send_photo(
                message.chat.id,
                thumb,
                caption=(
                    "🎶 **Now Playing**\n"
                    f"**{playable['title']}**\n"
                    f"Duration: "
                    f"{playable.get('duration_text', '?')}"
                ),
                reply_markup=stream_buttons(
                    message.chat.id
                ),
            )

        except Exception as exc:
            LOGGER.exception("Unable to start playback")

            error_message = (
                "❌ Unable to play this song.\n\n"
                f"Error: `{type(exc).__name__}`\n\n"
                "Check YouTube cookies and the stream logs."
            )

            try:
                await status.edit_text(error_message)
            except Exception:
                LOGGER.warning(
                    "Could not update playback status message."
                )

    @app.on_message(
        filters.command("play") & filters.group
    )
    async def play_command(client, message):
        await handle_play(
            client,
            message,
            force_video=False,
        )

    @app.on_message(
        filters.command("vplay") & filters.group
    )
    async def vplay_command(client, message):
        await handle_play(
            client,
            message,
            force_video=True,
        )

    @app.on_message(
        filters.regex(
            rf"(?i)^(?:{TRIGGER})\s+(play|vplay)\s+(.+)"
        )
        & filters.group
    )
    async def trigger_play_command(client, message):
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
