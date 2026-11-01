
import html
import logging

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode

from music import music_queue
from player_ui import format_duration, stylize


LOGGER = logging.getLogger(__name__)


async def is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )
    except Exception:
        return False


def track_title(track):
    return html.escape(
        str(track.get("title") or "Unknown Track")
    )


def track_duration(track):
    duration = track.get("duration", 0)

    try:
        return format_duration(int(duration))
    except (TypeError, ValueError):
        return "Unknown"


def register_queue_handlers(app, stream):

    # QUEUE COMMAND
    @app.on_message(filters.command("queue") & filters.group)
    async def queue_command(client, message):
        chat_id = message.chat.id

        current = await music_queue.get_current(chat_id)
        tracks = await music_queue.get_queue(chat_id)

        if not current and not tracks:
            return await message.reply_text(
                stylize("The queue is currently empty.")
            )

        lines = [f"🎶 {stylize('Adisha Music Queue')}"]

        if current:
            lines.append(
                f"\n▶️ {stylize('Now Playing')}\n"
                f"• {track_title(current)} "
                f"<code>[{track_duration(current)}]</code>"
            )

        if tracks:
            lines.append(f"\n📋 {stylize('Up Next')}")

            for index, track in enumerate(tracks[:20], start=1):
                lines.append(
                    f"\n<code>{index}.</code> "
                    f"{track_title(track)} "
                    f"<code>[{track_duration(track)}]</code>"
                )

            if len(tracks) > 20:
                lines.append(
                    f"\n{stylize('And')} "
                    f"{len(tracks) - 20} "
                    f"{stylize('more tracks...')}"
                )

        total = len(tracks) + (1 if current else 0)

        lines.append(
            f"\n\n{stylize('Total Tracks:')} "
            f"<code>{total}</code>"
        )

        loop_mode = await music_queue.get_loop(chat_id)
        shuffle_mode = await music_queue.is_shuffle(chat_id)

        lines.append(
            f"\n{stylize('Loop:')} "
            f"<code>{html.escape(str(loop_mode))}</code>"
        )

        lines.append(
            f"\n{stylize('Shuffle:')} "
            f"<code>{'ON' if shuffle_mode else 'OFF'}</code>"
        )

        await message.reply_text(
            "".join(lines),
            parse_mode=ParseMode.HTML,
        )

    # NOW PLAYING COMMAND
    @app.on_message(filters.command("now") & filters.group)
    async def now_command(client, message):
        current = await music_queue.get_current(message.chat.id)

        if not current:
            return await message.reply_text(
                stylize("Nothing is playing right now.")
            )

        title = track_title(current)
        duration = track_duration(current)

        await message.reply_text(
            f"🎧 {stylize('Now Playing')}\n\n"
            f"🎵 {title}\n"
            f"⏱ <code>{duration}</code>\n"
            f"🎼 {stylize('Adisha Music')}",
            parse_mode=ParseMode.HTML,
        )

    # LOOP COMMAND
    @app.on_message(filters.command("loop") & filters.group)
    async def loop_command(client, message):
        if not message.from_user or not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text(
                stylize("Only admins can change loop settings.")
            )

        args = message.text.split(maxsplit=1)
        mode = args[1].lower().strip() if len(args) > 1 else None

        if mode not in (None, "off", "track", "queue"):
            return await message.reply_text(
                f"{stylize('Usage:')} "
                f"<code>/loop off</code>, "
                f"<code>/loop track</code>, "
                f"<code>/loop queue</code>",
                parse_mode=ParseMode.HTML,
            )

        if mode is None:
            mode = await music_queue.cycle_loop(message.chat.id)
        else:
            await music_queue.set_loop(message.chat.id, mode)

        await message.reply_text(
            f"🔁 {stylize('Loop mode:')} "
            f"<code>{html.escape(str(mode))}</code>",
            parse_mode=ParseMode.HTML,
        )

    # SHUFFLE COMMAND
    @app.on_message(filters.command("shuffle") & filters.group)
    async def shuffle_command(client, message):
        if not message.from_user or not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text(
                stylize("Only admins can change shuffle settings.")
            )

        args = message.text.split(maxsplit=1)
        value = args[1].lower().strip() if len(args) > 1 else None

        if value not in (None, "on", "off"):
            return await message.reply_text(
                f"{stylize('Usage:')} "
                f"<code>/shuffle</code>, "
                f"<code>/shuffle on</code>, "
                f"<code>/shuffle off</code>",
                parse_mode=ParseMode.HTML,
            )

        current = await music_queue.is_shuffle(message.chat.id)

        if value == "on":
            enabled = True
        elif value == "off":
            enabled = False
        else:
            enabled = not current

        await music_queue.shuffle(
            message.chat.id,
            enabled=enabled,
        )

        await message.reply_text(
            f"🔀 {stylize('Shuffle:')} "
            f"<code>{'ON' if enabled else 'OFF'}</code>",
            parse_mode=ParseMode.HTML,
        )

    # REMOVE COMMAND
    @app.on_message(filters.command("remove") & filters.group)
    async def remove_command(client, message):
        if not message.from_user or not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text(
                stylize("Only admins can remove tracks.")
            )

        args = message.text.split(maxsplit=1)

        if len(args) < 2 or not args[1].isdigit():
            return await message.reply_text(
                f"{stylize('Usage:')} <code>/remove 1</code>",
                parse_mode=ParseMode.HTML,
            )

        position = int(args[1])

        if position < 1:
            return await message.reply_text(
                stylize("Invalid queue position.")
            )

        try:
            removed = await music_queue.remove(
                message.chat.id,
                position,
            )
        except Exception:
            LOGGER.exception("Queue remove failed")
            removed = None

        if not removed:
            return await message.reply_text(
                stylize("No track found at that position.")
            )

        await message.reply_text(
            f"🗑 {stylize('Removed:')} {track_title(removed)}",
            parse_mode=ParseMode.HTML,
        )

    # CLEAR UPCOMING QUEUE
    @app.on_message(filters.command("clearqueue") & filters.group)
    async def clear_queue_command(client, message):
        if not message.from_user or not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text(
                stylize("Only admins can clear the queue.")
            )

        try:
            await music_queue.clear_upcoming(message.chat.id)
        except Exception:
            LOGGER.exception("Clear queue failed")
            return await message.reply_text(
                stylize("Unable to clear the queue.")
            )

        await message.reply_text(
            stylize(
                "Upcoming queue cleared. Current track is still playing."
            )
        )

    LOGGER.info("Adisha Music queue handlers registered")
