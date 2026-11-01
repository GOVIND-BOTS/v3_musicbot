import html
import logging

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode

from music import music_queue

LOGGER = logging.getLogger(__name__)


async def _is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )
    except Exception:
        LOGGER.exception("Queue permission check failed.")
        return False


async def _require_admin(client, message):
    if not message.from_user or not await _is_admin(
        client, message.chat.id, message.from_user.id
    ):
        await message.reply_text(
            "❌ Only group admins can use this command."
        )
        return False
    return True


def _track_title(track):
    return html.escape(str(track.get("title") or "Unknown"))


def register_queue_handlers(app, stream):

    @app.on_message(filters.command("queue") & filters.group)
    async def queue_command(client, message):
        chat_id = message.chat.id
        current = await music_queue.get_current(chat_id)
        items = await music_queue.get_queue(chat_id)
        loop_mode = await music_queue.get_loop(chat_id)
        shuffled = await music_queue.is_shuffle(chat_id)

        lines = ["🎶 <b>Music Queue</b>", "━━━━━━━━━━━━━━━━━━"]

        if current:
            lines.append(f"▶️ <b>Now playing:</b> {_track_title(current)}")
        else:
            lines.append("⏹ <i>Nothing is playing right now.</i>")

        if items:
            lines.append("\n<b>Up next:</b>")
            for index, item in enumerate(items[:20], 1):
                duration = html.escape(str(item.get("duration_text") or ""))
                suffix = f" <code>[{duration}]</code>" if duration else ""
                lines.append(f"{index}. {_track_title(item)}{suffix}")
            if len(items) > 20:
                lines.append(f"\n…and {len(items) - 20} more song(s).")
        elif not current:
            lines.append("\nQueue is empty.")
        else:
            lines.append("\n<i>No upcoming songs.</i>")

        lines.append(
            f"\n🔁 <b>Loop:</b> {html.escape(loop_mode)}"
            f"\n🔀 <b>Shuffle:</b> {'On' if shuffled else 'Off'}"
        )

        await message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    @app.on_message(filters.command("now") & filters.group)
    async def now_command(client, message):
        current = await music_queue.get_current(message.chat.id)
        if not current:
            await message.reply_text("⏹ Nothing is playing right now.")
            return

        title = _track_title(current)
        duration = html.escape(str(current.get("duration_text") or "Unknown"))
        media_type = html.escape(str(current.get("media_type") or "audio").upper())

        await message.reply_text(
            "🎶 <b>Now Playing</b>\n"
            f"📌 {title}\n"
            f"⏱ Duration: {duration}\n"
            f"🎧 Type: {media_type}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    @app.on_message(filters.command("loop") & filters.group)
    async def loop_command(client, message):
        if not await _require_admin(client, message):
            return

        args = (message.text or "").split(maxsplit=1)
        requested = args[1].strip().lower() if len(args) > 1 else "cycle"
        aliases = {
            "0": "off", "disable": "off", "none": "off",
            "1": "track", "song": "track", "current": "track",
            "2": "queue", "all": "queue",
        }
        requested = aliases.get(requested, requested)

        try:
            if requested in ("cycle", "next"):
                mode = await music_queue.cycle_loop(message.chat.id)
            else:
                mode = await music_queue.set_loop(message.chat.id, requested)
        except ValueError:
            await message.reply_text(
                "Usage: <code>/loop off</code>, "
                "<code>/loop track</code> or <code>/loop queue</code>.",
                parse_mode=ParseMode.HTML,
            )
            return

        descriptions = {
            "off": "Loop disabled.",
            "track": "Current song will repeat.",
            "queue": "The queue will repeat continuously.",
        }
        await message.reply_text(
            f"🔁 {descriptions[mode]}",
            parse_mode=ParseMode.HTML,
        )

    @app.on_message(filters.command("shuffle") & filters.group)
    async def shuffle_command(client, message):
        if not await _require_admin(client, message):
            return

        args = (message.text or "").split(maxsplit=1)
        requested = args[1].strip().lower() if len(args) > 1 else "toggle"

        if requested in ("on", "yes", "true", "enable", "enabled"):
            enabled = True
        elif requested in ("off", "no", "false", "disable", "disabled"):
            enabled = False
        elif requested in ("toggle", ""):
            enabled = None
        else:
            await message.reply_text(
                "Usage: <code>/shuffle</code>, "
                "<code>/shuffle on</code> or <code>/shuffle off</code>.",
                parse_mode=ParseMode.HTML,
            )
            return

        state = await music_queue.shuffle(message.chat.id, enabled)
        await message.reply_text(
            "🔀 Shuffle enabled." if state else "🔀 Shuffle disabled."
        )

    @app.on_message(filters.command("remove") & filters.group)
    async def remove_command(client, message):
        if not await _require_admin(client, message):
            return

        args = (message.text or "").split(maxsplit=1)
        if len(args) < 2 or not args[1].strip().isdigit():
            await message.reply_text(
                "Usage: <code>/remove 1</code>\n"
                "The number refers to the upcoming queue position.",
                parse_mode=ParseMode.HTML,
            )
            return

        position = int(args[1].strip())
        removed = await music_queue.remove(message.chat.id, position)

        if removed is None:
            await message.reply_text("❌ That queue position does not exist.")
            return

        await message.reply_text(
            f"🗑 Removed: <b>{_track_title(removed)}</b>",
            parse_mode=ParseMode.HTML,
        )

    @app.on_message(filters.command("clearqueue") & filters.group)
    async def clearqueue_command(client, message):
        if not await _require_admin(client, message):
            return

        try:
            await stream.stop(message.chat.id)
        except Exception:
            LOGGER.exception("Could not stop stream while clearing queue.")
            await music_queue.clear(message.chat.id)

        await message.reply_text("🧹 Queue cleared and playback stopped.")
