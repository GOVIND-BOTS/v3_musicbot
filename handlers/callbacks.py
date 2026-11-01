
import asyncio
import logging
import time
from contextlib import suppress
from html import escape

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import InputMediaPhoto

from music import music_queue
from buttons import queue_buttons, stream_buttons
from database.mongodb import get_chat_settings
from player_ui import format_duration, stylize, now_playing_caption

LOGGER = logging.getLogger(__name__)

_PROGRESS_TASKS = {}
_PROGRESS_STATE = {}


def _get_elapsed(chat_id):
    state = _PROGRESS_STATE.get(chat_id)

    if not state:
        return 0

    elapsed = state["elapsed"]

    if not state["paused"]:
        elapsed += time.monotonic() - state["started_at"]

    duration = state["duration"]

    if duration > 0:
        elapsed = min(elapsed, duration)

    return max(0, int(elapsed))


def start_progress_updater(client, chat_id, track, stream):
    stop_progress_updater(chat_id)

    try:
        duration = float(track.get("duration", 0) or 0)
    except (TypeError, ValueError):
        duration = 0

    _PROGRESS_STATE[chat_id] = {
        "track": track,
        "duration": max(0, duration),
        "elapsed": 0,
        "started_at": time.monotonic(),
        "paused": False,
    }

    _PROGRESS_TASKS[chat_id] = asyncio.create_task(
        _progress_loop(client, chat_id, stream)
    )


def stop_progress_updater(chat_id):
    task = _PROGRESS_TASKS.pop(chat_id, None)

    if task and not task.done():
        task.cancel()

    _PROGRESS_STATE.pop(chat_id, None)


def pause_progress_updater(chat_id):
    state = _PROGRESS_STATE.get(chat_id)

    if not state or state["paused"]:
        return

    state["elapsed"] = _get_elapsed(chat_id)
    state["paused"] = True


def resume_progress_updater(chat_id):
    state = _PROGRESS_STATE.get(chat_id)

    if not state or not state["paused"]:
        return

    state["started_at"] = time.monotonic()
    state["paused"] = False


def replay_progress_updater(chat_id):
    state = _PROGRESS_STATE.get(chat_id)

    if not state:
        return

    state["elapsed"] = 0
    state["started_at"] = time.monotonic()
    state["paused"] = False


async def refresh_player_keyboard(client, chat_id, stream):
    message = stream.player_messages.get(chat_id)
    state = _PROGRESS_STATE.get(chat_id)

    if not message or not state:
        return

    try:
        loop_mode = await music_queue.get_loop(chat_id)
        shuffle_enabled = await music_queue.is_shuffle(chat_id)

        keyboard = stream_buttons(
            chat_id,
            elapsed=_get_elapsed(chat_id),
            duration=state["duration"],
            loop_mode=loop_mode,
            shuffle=shuffle_enabled,
        )

        await message.edit_reply_markup(reply_markup=keyboard)

    except Exception as error:
        LOGGER.debug(
            "Player keyboard refresh failed in %s: %s",
            chat_id,
            error,
        )


async def _progress_loop(client, chat_id, stream):
    try:
        while chat_id in _PROGRESS_STATE:
            await asyncio.sleep(8)

            if chat_id not in _PROGRESS_STATE:
                break

            await refresh_player_keyboard(
                client,
                chat_id,
                stream,
            )

    except asyncio.CancelledError:
        pass

    except Exception:
        LOGGER.exception(
            "Progress updater failed in chat %s",
            chat_id,
        )


async def update_player_message(client, player_message, track, chat_id, stream):
    if not track:
        return None

    caption = now_playing_caption(track)
    thumbnail = track.get("thumbnail")

    try:
        duration = float(track.get("duration", 0) or 0)
    except (TypeError, ValueError):
        duration = 0

    loop_mode = await music_queue.get_loop(chat_id)
    shuffle_enabled = await music_queue.is_shuffle(chat_id)

    keyboard = stream_buttons(
        chat_id,
        elapsed=0,
        duration=duration,
        loop_mode=loop_mode,
        shuffle=shuffle_enabled,
    )

    if player_message:
        try:
            if getattr(player_message, "photo", None):
                if thumbnail:
                    await player_message.edit_media(
                        media=InputMediaPhoto(
                            media=thumbnail,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                        ),
                        reply_markup=keyboard,
                    )
                else:
                    await player_message.edit_caption(
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                    )
            else:
                await player_message.edit_text(
                    text=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )

            stream.player_messages[chat_id] = player_message

            start_progress_updater(
                client,
                chat_id,
                track,
                stream,
            )

            return player_message

        except Exception:
            LOGGER.warning(
                "Could not edit old player message in chat %s. "
                "Sending a new one.",
                chat_id,
                exc_info=True,
            )

    try:
        if thumbnail:
            new_message = await client.send_photo(
                chat_id,
                photo=thumbnail,
                caption=caption,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )
        else:
            new_message = await client.send_message(
                chat_id,
                text=caption,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )

        stream.player_messages[chat_id] = new_message

        start_progress_updater(
            client,
            chat_id,
            track,
            stream,
        )

        return new_message

    except Exception:
        LOGGER.exception(
            "Could not send updated player message in chat %s",
            chat_id,
        )
        return None


async def is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)

        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )
    except Exception:
        return False


async def is_authorized(client, chat_id, user_id):
    if await is_admin(client, chat_id, user_id):
        return True

    try:
        settings = await get_chat_settings(chat_id) or {}
        authorized_users = settings.get("authorized_users", [])

        return int(user_id) in {
            int(uid) for uid in authorized_users
        }

    except Exception:
        LOGGER.exception(
            "Authorization check failed in %s",
            chat_id,
        )
        return False


async def build_queue_text(chat_id):
    current = await music_queue.get_current(chat_id)
    tracks = await music_queue.get_queue(chat_id)

    lines = [
        f"<b>🎶 {stylize('Adisha Music Queue')}</b>",
        "",
    ]

    if current:
        title = escape(str(current.get("title", "Unknown")))
        duration = current.get("duration_text") or format_duration(
            current.get("duration", 0)
        )

        lines.extend([
            f"▶️ <b>{stylize('Now Playing')}</b>",
            f"• {title} — {escape(str(duration))}",
            "",
        ])
    else:
        lines.extend([
            f"<i>{stylize('Nothing is playing right now.')}</i>",
            "",
        ])

    lines.append(f"<b>{stylize('Upcoming Tracks')}</b>")

    if tracks:
        for index, track in enumerate(tracks[:15], start=1):
            title = escape(str(track.get("title", "Unknown")))
            duration = track.get("duration_text") or format_duration(
                track.get("duration", 0)
            )

            lines.append(
                f"{index}. {title} — {escape(str(duration))}"
            )

        if len(tracks) > 15:
            lines.append(
                f"\n{stylize('And')} {len(tracks) - 15} "
                f"{stylize('more tracks...')}"
            )
    else:
        lines.append(f"<i>{stylize('No upcoming tracks.')}</i>")

    return "\n".join(lines)


def register_callback_handlers(app, stream):

    @app.on_callback_query(filters.regex(r"^ctrl_"))
    async def player_callbacks(client, query):
        data = query.data or ""
        message = query.message
        user = query.from_user

        if not message or not user:
            await query.answer(
                stylize("Invalid player message."),
                show_alert=True,
            )
            return

        chat_id = message.chat.id

        try:
            parts = data.split("|")
            action = parts[0]

            if action == "ctrl_close":
                if not await is_authorized(client, chat_id, user.id):
                    await query.answer(
                        stylize("You are not allowed to close this player."),
                        show_alert=True,
                    )
                    return

                await query.answer(stylize("Player closed."))

                try:
                    await message.delete()
                except Exception:
                    pass

                current_message = stream.player_messages.get(chat_id)

                if current_message and current_message.id == message.id:
                    stream.player_messages.pop(chat_id, None)
                    stop_progress_updater(chat_id)

                return

            if len(parts) < 2:
                await query.answer(
                    stylize("Invalid player command."),
                    show_alert=True,
                )
                return

            try:
                target_chat = int(parts[1])
            except (ValueError, TypeError):
                await query.answer(
                    stylize("Invalid chat ID."),
                    show_alert=True,
                )
                return

            if target_chat != chat_id:
                await query.answer(
                    stylize("This player belongs to another chat."),
                    show_alert=True,
                )
                return

            if not await is_authorized(client, chat_id, user.id):
                await query.answer(
                    stylize(
                        "Only admins and authorized users can control music."
                    ),
                    show_alert=True,
                )
                return

            if action == "ctrl_progress":
                await query.answer(
                    stylize("Playback progress updates automatically.")
                )
                return

            if action == "ctrl_queue":
                queue_text = await build_queue_text(chat_id)
                loop_mode = await music_queue.get_loop(chat_id)
                shuffle_enabled = await music_queue.is_shuffle(chat_id)

                await query.answer()

                await message.reply_text(
                    queue_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=queue_buttons(
                        chat_id,
                        loop_mode=loop_mode,
                        shuffle=shuffle_enabled,
                    ),
                )
                return

            if action == "ctrl_pause":
                result = await stream.pause(chat_id)

                if result:
                    pause_progress_updater(chat_id)
                    await refresh_player_keyboard(client, chat_id, stream)

                await query.answer(
                    stylize(
                        "Playback paused."
                        if result else "Nothing is playing."
                    ),
                    show_alert=not result,
                )
                return

            if action == "ctrl_resume":
                result = await stream.resume(chat_id)

                if result:
                    resume_progress_updater(chat_id)
                    await refresh_player_keyboard(client, chat_id, stream)

                await query.answer(
                    stylize(
                        "Playback resumed."
                        if result else "Nothing is playing."
                    ),
                    show_alert=not result,
                )
                return

            if action == "ctrl_skip":
                track = await stream.skip(chat_id)

                if isinstance(track, dict):
                    player_message = stream.player_messages.get(chat_id)

                    await update_player_message(
                        client,
                        player_message,
                        track,
                        chat_id,
                        stream,
                    )
                else:
                    stop_progress_updater(chat_id)

                await query.answer(
                    stylize(
                        "Skipped to next track."
                        if track else "Queue is empty."
                    ),
                    show_alert=not bool(track),
                )
                return

            if action == "ctrl_stop":
                await stream.stop(chat_id)
                stop_progress_updater(chat_id)
                stream.player_messages.pop(chat_id, None)

                await query.answer(stylize("Playback stopped."))

                try:
                    await message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass

                return

            if action == "ctrl_replay":
                track = await stream.replay(chat_id)

                if track:
                    replay_progress_updater(chat_id)
                    await refresh_player_keyboard(client, chat_id, stream)

                await query.answer(
                    stylize(
                        "Track restarted."
                        if track else "Nothing is playing."
                    ),
                    show_alert=not bool(track),
                )
                return

            if action == "ctrl_loop":
                mode = await music_queue.cycle_loop(chat_id)

                await refresh_player_keyboard(client, chat_id, stream)

                await query.answer(
                    f"{stylize('Loop')}: {str(mode).upper()}"
                )
                return

            if action == "ctrl_shuffle":
                enabled = await music_queue.shuffle(chat_id)

                await refresh_player_keyboard(client, chat_id, stream)

                await query.answer(
                    f"{stylize('Shuffle')}: "
                    f"{stylize('ON' if enabled else 'OFF')}"
                )
                return

            await query.answer(
                stylize("Unknown player command."),
                show_alert=True,
            )

        except Exception:
            LOGGER.exception(
                "Player callback failed in chat %s",
                chat_id,
            )

            await query.answer(
                stylize("Something went wrong. Please try again."),
                show_alert=True,
            )
