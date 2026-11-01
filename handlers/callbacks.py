
import logging
from html import escape

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode

from music import music_queue
from buttons import queue_buttons
from Mongodb import get_chat_settings
from player_ui import format_duration, stylize


LOGGER = logging.getLogger(__name__)


# ----------------------------------
# ADMIN CHECK
# ----------------------------------

async def is_admin(client, chat_id, user_id):

    try:
        member = await client.get_chat_member(
            chat_id,
            user_id,
        )

        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )

    except Exception:
        return False


# ----------------------------------
# AUTHORIZED USER CHECK
# ----------------------------------

async def is_authorized(client, chat_id, user_id):

    if await is_admin(client, chat_id, user_id):
        return True

    try:
        settings = await get_chat_settings(
            chat_id
        )

        authorized_users = settings.get(
            "authorized_users",
            [],
        )

        return int(user_id) in {
            int(uid) for uid in authorized_users
        }

    except Exception:

        LOGGER.exception(
            "Authorization check failed in %s",
            chat_id,
        )

        return False


# ----------------------------------
# QUEUE TEXT
# ----------------------------------

async def build_queue_text(chat_id):

    current = await music_queue.get_current(
        chat_id
    )

    tracks = await music_queue.get_queue(
        chat_id
    )

    loop_mode = await music_queue.get_loop(
        chat_id
    )

    shuffle_enabled = await music_queue.is_shuffle(
        chat_id
    )

    lines = [
        f"<b>🎶 {stylize('Adisha Music Queue')}</b>",
        "",
    ]

    if current:

        title = escape(
            str(current.get("title", "Unknown"))
        )

        duration = current.get(
            "duration_text"
        ) or format_duration(
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

    lines.append(
        f"<b>{stylize('Upcoming Tracks')}</b>"
    )

    if tracks:

        for index, track in enumerate(
            tracks[:15],
            start=1,
        ):

            title = escape(
                str(track.get("title", "Unknown"))
            )

            duration = track.get(
                "duration_text"
            ) or format_duration(
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

        lines.append(
            f"<i>{stylize('No upcoming tracks.')}</i>"
        )

    lines.extend([
        "",
        f"<b>{stylize('Loop')}:</b> {escape(str(loop_mode).upper())}",
        f"<b>{stylize('Shuffle')}:</b> "
        f"{stylize('ON' if shuffle_enabled else 'OFF')}",
    ])

    return "\n".join(lines)


# ----------------------------------
# CALLBACK REGISTRATION
# ----------------------------------

def register_callback_handlers(app, stream):

    @app.on_callback_query(
        filters.regex(r"^ctrl_")
    )
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

            # ----------------------------------
            # CLOSE
            # ----------------------------------

            if action == "ctrl_close":

                if not await is_authorized(
                    client,
                    chat_id,
                    user.id,
                ):

                    await query.answer(
                        stylize("You are not allowed to close this player."),
                        show_alert=True,
                    )
                    return

                await query.answer(
                    stylize("Player closed.")
                )

                try:
                    await message.delete()
                except Exception:
                    pass

                return

            # ----------------------------------
            # CHAT VALIDATION
            # ----------------------------------

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

            # ----------------------------------
            # PERMISSION
            # ----------------------------------

            if not await is_authorized(
                client,
                chat_id,
                user.id,
            ):

                await query.answer(
                    stylize(
                        "Only admins and authorized users can control music."
                    ),
                    show_alert=True,
                )
                return

            # ----------------------------------
            # QUEUE
            # ----------------------------------

            if action == "ctrl_queue":

                queue_text = await build_queue_text(
                    chat_id
                )

                await query.answer()

                await message.reply_text(
                    queue_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=queue_buttons(chat_id),
                )

                return

            # ----------------------------------
            # PAUSE
            # ----------------------------------

            if action == "ctrl_pause":

                result = await stream.pause(
                    chat_id
                )

                await query.answer(
                    stylize(
                        "Playback paused."
                        if result
                        else "Nothing is playing."
                    ),
                    show_alert=not result,
                )

                return

            # ----------------------------------
            # RESUME
            # ----------------------------------

            if action == "ctrl_resume":

                result = await stream.resume(
                    chat_id
                )

                await query.answer(
                    stylize(
                        "Playback resumed."
                        if result
                        else "Nothing is playing."
                    ),
                    show_alert=not result,
                )

                return

            # ----------------------------------
            # SKIP
            # ----------------------------------

            if action == "ctrl_skip":

                track = await stream.skip(
                    chat_id
                )

                await query.answer(
                    stylize(
                        "Skipped to next track."
                        if track
                        else "Queue is empty."
                    ),
                    show_alert=not bool(track),
                )

                return

            # ----------------------------------
            # STOP
            # ----------------------------------

            if action == "ctrl_stop":

                await stream.stop(
                    chat_id
                )

                await query.answer(
                    stylize("Playback stopped.")
                )

                try:
                    await message.edit_reply_markup(
                        reply_markup=None
                    )
                except Exception:
                    pass

                return

            # ----------------------------------
            # REPLAY
            # ----------------------------------

            if action == "ctrl_replay":

                track = await stream.replay(
                    chat_id
                )

                await query.answer(
                    stylize(
                        "Track restarted."
                        if track
                        else "Nothing is playing."
                    ),
                    show_alert=not bool(track),
                )

                return

            # ----------------------------------
            # LOOP
            # ----------------------------------

            if action == "ctrl_loop":

                mode = await music_queue.cycle_loop(
                    chat_id
                )

                await query.answer(
                    f"{stylize('Loop')}: {str(mode).upper()}"
                )

                return

            # ----------------------------------
            # SHUFFLE
            # ----------------------------------

            if action == "ctrl_shuffle":

                enabled = await music_queue.shuffle(
                    chat_id
                )

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
