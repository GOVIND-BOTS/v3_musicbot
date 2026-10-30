
import logging
from html import escape

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InputMediaPhoto

from music import music_queue
from buttons import queue_buttons, stream_buttons
from thumbnails import get_thumb
from player_ui import now_playing_caption


LOGGER = logging.getLogger(__name__)


async def update_player_message(message, track, chat_id):
    """Update the existing player message with the new track."""

    if not isinstance(track, dict):
        return

    title = track.get("title") or "Unknown Track"

    try:
        thumb = await get_thumb(
            track.get("videoid"),
            title,
            track.get("duration_text") or track.get("duration"),
            track.get("views", 0),
            track.get("channel", "YouTube"),
            "GOVIND MUSIC",
            track.get("requested_by_name", "Group member"),
        )

        caption = now_playing_caption(track)

        if thumb:
            await message.edit_media(
                InputMediaPhoto(
                    media=thumb,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                ),
                reply_markup=stream_buttons(chat_id),
            )
        else:
            await message.edit_caption(
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=stream_buttons(chat_id),
            )

    except Exception:
        LOGGER.exception("Failed to update player message")


def register_callback_handlers(app, stream):

    @app.on_callback_query(filters.regex(r"^ctrl_"))
    async def player_controls(client, query):

        data = query.data or ""

        if data == "ctrl_close":
            await query.answer()

            try:
                await query.message.delete()
            except Exception:
                pass

            return

        parts = data.split("|")

        action = parts[0]

        try:
            chat_id = (
                int(parts[1])
                if len(parts) > 1
                else query.message.chat.id
            )
        except (TypeError, ValueError):
            await query.answer(
                "Invalid chat ID",
                show_alert=True,
            )
            return

        try:

            # QUEUE
            if action == "ctrl_queue":

                items = await music_queue.get_queue(chat_id)
                current = await music_queue.get_current(chat_id)

                text = "🎶 <b>GOVIND MUSIC QUEUE</b>\n"

                if current:
                    text += (
                        "\n▶️ <b>Currently Playing:</b>\n"
                        f"{escape(str(current.get('title', 'Unknown')))}\n"
                        "👤 Requested by: "
                        f"{escape(str(current.get('requested_by_name', 'Group member')))}\n"
                    )

                if not items:
                    text += "\n📭 Queue is empty."
                else:
                    text += "\n<b>Up Next:</b>\n"

                    for index, track in enumerate(items, 1):
                        title = escape(
                            str(track.get("title", "Unknown"))
                        )

                        requester = escape(
                            str(track.get("requested_by_name", "Group member"))
                        )

                        text += (
                            f"\n{index}. 🎵 {title}\n"
                            f"   👤 {requester}\n"
                        )

                await query.answer()

                await query.message.reply_text(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=queue_buttons(chat_id),
                )

                return

            # PAUSE
            if action == "ctrl_pause":

                await stream.pause(chat_id)
                answer = "⏸ Music paused."

            # RESUME
            elif action == "ctrl_resume":

                await stream.resume(chat_id)
                answer = "▶️ Music resumed."

            # SKIP
            elif action == "ctrl_skip":

                track = await stream.skip(chat_id)

                if track and isinstance(track, dict):

                    await update_player_message(
                        query.message,
                        track,
                        chat_id,
                    )

                    answer = (
                        "⏭ Skipped to: "
                        f"{track.get('title', 'Next track')}"
                    )

                else:
                    answer = "Queue finished. No next song."

            # STOP
            elif action == "ctrl_stop":

                await stream.stop(chat_id)
                answer = "⏹ Music stopped."

            # REPLAY
            elif action == "ctrl_replay":

                track = await stream.replay(chat_id)

                if isinstance(track, dict):
                    await update_player_message(
                        query.message,
                        track,
                        chat_id,
                    )

                    answer = "↻ Replaying current track."

                else:
                    current = await music_queue.get_current(chat_id)

                    if isinstance(current, dict):
                        await update_player_message(
                            query.message,
                            current,
                            chat_id,
                        )

                    answer = "↻ Replay requested."

            else:
                answer = "Unknown control."

            await query.answer(answer)

        except Exception as exc:

            LOGGER.exception(
                "Player callback failed: %s",
                action,
            )

            try:
                await query.answer(
                    f"Action failed: {type(exc).__name__}",
                    show_alert=True,
                )
            except Exception:
                pass
