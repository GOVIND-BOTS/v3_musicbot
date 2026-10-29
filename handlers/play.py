
import logging
import time

from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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

PENDING_TRACKS = {}
PENDING_TTL = 900


async def safe_edit(message, text, **kwargs):
    try:
        await message.edit_text(text, **kwargs)
        return True
    except FloodWait as exc:
        LOGGER.warning(
            "Telegram FloodWait during status edit: %s seconds",
            getattr(exc, "value", "unknown"),
        )
    except Exception:
        LOGGER.debug("Status edit failed.", exc_info=True)

    return False


def clean_pending():
    now = time.time()

    for key, value in list(PENDING_TRACKS.items()):
        if now - value.get("time", 0) > PENDING_TTL:
            PENDING_TRACKS.pop(key, None)


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
                    f"`/play song name` or `{TRIGGER} play song name`\n"
                    f"`/vplay song name` or `{TRIGGER} vplay song name`"
                )
                return

            query_text = " ".join(message.command[1:]).strip()

        status = await message.reply_text("🔎 Searching YouTube...")

        try:
            if is_youtube_url(query_text):
                results = [await get_video_info(query_text)]
            else:
                results = await search_youtube(query_text, limit=5)

            results = [
                item for item in results
                if item and item.get("webpage_url")
            ]

            if not results:
                await safe_edit(
                    status,
                    "No results found. Try another title.",
                )
                return

            clean_pending()

            if len(results) == 1:
                track = results[0]
                media_type = "video" if force_video else "audio"

                await safe_edit(
                    status,
                    f"⏳ Preparing {media_type} stream...",
                )

                playable = await get_stream_url(
                    track["webpage_url"],
                    media_type,
                )

                result = await stream.play(
                    message.chat.id,
                    playable,
                    media_type,
                )

                if result == "queued":
                    await safe_edit(
                        status,
                        f"➕ Added to queue: **{playable['title']}**",
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

                try:
                    await status.delete()
                except Exception:
                    pass

                await client.send_photo(
                    message.chat.id,
                    thumb,
                    caption=(
                        "🎶 **Now Playing**\n"
                        f"**{playable['title']}**\n"
                        "Duration: "
                        f"{playable.get('duration_text', '?')}"
                    ),
                    reply_markup=stream_buttons(message.chat.id),
                )
                return

            user_id = message.from_user.id if message.from_user else 0
            key = (
                f"{message.chat.id}:"
                f"{user_id}:"
                f"{time.time_ns() // 1_000_000}"
            )

            PENDING_TRACKS[key] = {
                "items": results,
                "chat_id": message.chat.id,
                "user_id": user_id,
                "time": time.time(),
                "force_video": force_video,
            }

            rows = []

            for index, item in enumerate(results):
                title = (item.get("title") or "Unknown title")[:45]
                rows.append([
                    InlineKeyboardButton(
                        f"{index + 1}. {title}",
                        callback_data=f"select_track|{key}|{index}",
                    )
                ])

            rows.append([
                InlineKeyboardButton(
                    "✖ Close",
                    callback_data="ctrl_close",
                )
            ])

            await safe_edit(
                status,
                "**Choose a track:**",
                reply_markup=InlineKeyboardMarkup(rows),
            )

        except Exception as exc:
            LOGGER.exception("YouTube search/play failed")
            await safe_edit(
                status,
                "Could not search/play this track: "
                f"`{type(exc).__name__}`",
            )

    @app.on_message(filters.command("play") & filters.group)
    async def play_command(client, message):
        await handle_play(client, message, False)

    @app.on_message(filters.command("vplay") & filters.group)
    async def vplay_command(client, message):
        await handle_play(client, message, True)

    @app.on_message(
        filters.regex(
            rf"(?i)^(?:{TRIGGER})\s+(play|vplay)\s+(.+)"
        )
        & filters.group
    )
    async def trigger_play_command(client, message):
        match = message.matches[0] if message.matches else None

        if not match:
            return

        command = match.group(1).lower()
        query_text = match.group(2).strip()

        await handle_play(
            client,
            message,
            force_video=(command == "vplay"),
            query_text=query_text,
        )

    @app.on_callback_query(filters.regex(r"^select_track\|"))
    async def select_track(client, query):
        try:
            parts = query.data.split("|", 2)

            if len(parts) != 3:
                await query.answer(
                    "Invalid selection. Search again.",
                    show_alert=True,
                )
                return

            _, key, index_text = parts
            clean_pending()
            pending = PENDING_TRACKS.get(key)

            if not pending:
                await query.answer(
                    "This selection has expired. Search again.",
                    show_alert=True,
                )
                return

            clicker_id = query.from_user.id if query.from_user else 0

            if clicker_id != pending.get("user_id"):
                await query.answer(
                    "Please use your own song selection.",
                    show_alert=True,
                )
                return

            try:
                index = int(index_text)
            except (TypeError, ValueError):
                await query.answer("Invalid track number.", show_alert=True)
                return

            items = pending.get("items") or []

            if index < 0 or index >= len(items):
                await query.answer("Track not found.", show_alert=True)
                return

            await query.answer("Preparing stream...")

            track = items[index]
            media_type = (
                "video" if pending.get("force_video") else "audio"
            )

            await safe_edit(
                query.message,
                f"⏳ Preparing {media_type} stream...",
            )

            playable = await get_stream_url(
                track["webpage_url"],
                media_type,
            )

            result = await stream.play(
                pending["chat_id"],
                playable,
                media_type,
            )

            PENDING_TRACKS.pop(key, None)

            if result == "queued":
                await safe_edit(
                    query.message,
                    f"➕ Added to queue: **{playable['title']}**",
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

            try:
                await query.message.delete()
            except Exception:
                pass

            await client.send_photo(
                pending["chat_id"],
                thumb,
                caption=(
                    "🎶 **Now Playing**\n"
                    f"**{playable['title']}**\n"
                    "Duration: "
                    f"{playable.get('duration_text', '?')}"
                ),
                reply_markup=stream_buttons(pending["chat_id"]),
            )

        except Exception as exc:
            LOGGER.exception("Unable to start stream")

            try:
                await query.answer(
                    "Playback failed. Please try another track.",
                    show_alert=True,
                )
            except Exception:
                pass

            await safe_edit(
                query.message,
                "Unable to start playback: "
                f"`{type(exc).__name__}`",
            )
