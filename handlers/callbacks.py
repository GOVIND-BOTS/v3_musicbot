
import logging
from html import escape

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import InputMediaPhoto

from music import music_queue
from buttons import queue_buttons, stream_buttons
from thumbnails import get_thumb
from player_ui import now_playing_caption


LOGGER = logging.getLogger(__name__)


async def is_admin(client, chat_id, user_id):
    """Check whether the user is a group administrator."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )
    except Exception:
        return False


async def update_player_message(
    client,
    message,
    track,
    chat_id,
    stream,
):
    """Update the existing player card for the next track."""

    if not isinstance(track, dict):
        return None

    title = track.get("title") or "Unknown Track"
    thumb = None

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
        keyboard = stream_buttons(chat_id)

        if thumb:
            updated = await message.edit_media(
                InputMediaPhoto(
                    media=thumb,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                ),
                reply_markup=keyboard,
            )
        else:
            updated = await message.edit_caption(
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )

        if updated:
            stream.player_messages[chat_id] = updated

        return updated

    except Exception:
        LOGGER.warning(
            "Could not edit player card in chat %s",
            chat_id,
            exc_info=True,
        )

    try:
        if thumb:
            sent = await client.send_photo(
                chat_id,
                photo=thumb,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
        else:
            sent = await client.send_message(
                chat_id,
                caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )

        stream.player_messages[chat_id] = sent
        return sent

    except Exception:
        LOGGER.exception(
            "Could not send replacement player card in %s",
            chat_id,
        )
        return None


def register_callback_handlers(app, stream):

    @app.on_callback_query(filters.regex(r"^ctrl_"))
    async def player_controls(client, query):

        data = query.data or ""
        parts = data.split("|")
        action = parts[0]

        if not query.message:
            await query.answer(
                "Message not available.",
                show_alert=True,
            )
            return

        try:
            chat_id = (
                int(parts[1])
                if len(parts) > 1
                else query.message.chat.id
            )
        except (TypeError, ValueError):
            await query.answer(
                "Invalid chat ID.",
                show_alert=True,
            )
            return

        # Prevent a callback from controlling another chat.
        if chat_id != query.message.chat.id:
            await query.answer(
                "Invalid player message.",
                show_alert=True,
            )
            return

        # CLOSE does not control playback.
        if action == "ctrl_close":
            await query.answer()

            try:
                stored = stream.player_messages.get(chat_id)

                if stored and stored.id == query.message.id:
                    stream.player_messages.pop(chat_id, None)

                await query.message.delete()

            except Exception:
                LOGGER.exception("Could not close player message.")

            return

        # All playback controls require group admin permission.
        if not await is_admin(
            client,
            chat_id,
            query.from_user.id,
        ):
            await query.answer(
                "Only group admins can control the music.",
                show_alert=True,
            )
            return

        try:

            # SHOW QUEUE
            if action == "ctrl_queue":
                current = await music_queue.get_current(chat_id)
                items = await music_queue.get_queue(chat_id)

                text = "🎶 <b>GOVIND MUSIC QUEUE</b>\n"

                if current:
                    text += (
                        "\n▶️ <b>Now Playing:</b>\n"
                        f"🎵 {escape(str(current.get('title', 'Unknown')))}\n"
                        "👤 "
                        f"{escape(str(current.get('requested_by_name', 'Group member')))}\n"
                    )

                if items:
                    text += "\n<b>Up Next:</b>\n"

                    for index, track in enumerate(items, 1):
                        title = escape(
                            str(track.get("title", "Unknown"))
                        )
                        requester = escape(
                            str(
                                track.get(
                                    "requested_by_name",
                                    "Group member",
                                )
                            )
                        )

                        text += (
                            f"\n{index}. 🎵 {title}\n"
                            f"   👤 {requester}\n"
                        )
                elif not current:
                    text += "\n📭 Queue is empty."
                else:
                    text += "\n📭 No upcoming songs."

                await query.answer("Queue opened.")

                await query.message.reply_text(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=queue_buttons(chat_id),
                )
                return

            # PAUSE
            elif action == "ctrl_pause":
                success = await stream.pause(chat_id)
                answer = (
                    "⏸ Music paused."
                    if success
                    else "No music is currently playing."
                )

            # RESUME
            elif action == "ctrl_resume":
                success = await stream.resume(chat_id)
                answer = (
                    "▶️ Music resumed."
                    if success
                    else "No paused music found."
                )

            # SKIP
            elif action == "ctrl_skip":
                track = await stream.skip(chat_id)

                if track:
                    player_message = (
                        stream.player_messages.get(chat_id)
                        or query.message
                    )

                    await update_player_message(
                        client,
                        player_message,
                        track,
                        chat_id,
                        stream,
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

                stream.player_messages.pop(chat_id, None)

                try:
                    await query.message.edit_reply_markup(
                        reply_markup=None
                    )
                except Exception:
                    pass

                answer = "⏹ Music stopped and queue cleared."

            # REPLAY
            elif action == "ctrl_replay":
                track = await stream.replay(chat_id)

                if track:
                    player_message = (
                        stream.player_messages.get(chat_id)
                        or query.message
                    )

                    await update_player_message(
                        client,
                        player_message,
                        track,
                        chat_id,
                        stream,
                    )

                    answer = "↻ Replaying current track."
                else:
                    answer = "No track is currently playing."

            # LOOP: OFF → TRACK → QUEUE
            elif action == "ctrl_loop":
                mode = await music_queue.cycle_loop(chat_id)

                labels = {
                    "off": "Loop disabled",
                    "track": "Loop current track",
                    "queue": "Loop entire queue",
                }

                answer = f"🔁 {labels[mode]}."

            # SHUFFLE
            elif action == "ctrl_shuffle":
                enabled = await music_queue.shuffle(chat_id)

                answer = (
                    "🔀 Shuffle enabled."
                    if enabled
                    else "➡️ Shuffle disabled."
                )

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
