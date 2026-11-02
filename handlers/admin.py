
import logging

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus

from config import TRIGGER
from .callbacks import (
    update_player_message,
    pause_progress_updater,
    resume_progress_updater,
    stop_progress_updater,
)


LOGGER = logging.getLogger(__name__)


async def _is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)

        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )

    except Exception:
        LOGGER.exception("Admin permission check failed.")
        return False


def register_admin_handlers(app, stream):

    async def admin_action(client, message, action):

        if (
            not message.from_user
            or not await _is_admin(
                client,
                message.chat.id,
                message.from_user.id,
            )
        ):
            await message.reply_text(
                "Only group admins can use this command."
            )
            return

        chat_id = message.chat.id

        try:
            if action == "pause":
                success = await stream.pause(chat_id)

                if success:
                    pause_progress_updater(chat_id)

                text = (
                    "⏸ Playback paused."
                    if success
                    else "No music is currently playing."
                )

            elif action == "resume":
                success = await stream.resume(chat_id)

                if success:
                    resume_progress_updater(chat_id)

                text = (
                    "▶️ Playback resumed."
                    if success
                    else "No paused music found."
                )

            elif action == "skip":
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

                    text = (
                        "⏭ Skipped. Now playing:\n"
                        f"{track.get('title', 'Next track')}"
                    )

                else:
                    stop_progress_updater(chat_id)
                    text = "✅ Queue finished. No next song."

            elif action == "stop":
                await stream.stop(chat_id)

                stop_progress_updater(chat_id)
                stream.player_messages.pop(chat_id, None)

                text = "⏹ Playback stopped and queue cleared."

            else:
                return

            await message.reply_text(text)

        except Exception as exc:
            LOGGER.exception(
                "Admin command failed: %s",
                action,
            )

            await message.reply_text(
                f"❌ Command failed: `{type(exc).__name__}`"
            )

    @app.on_message(
        filters.command("pause") & filters.group
    )
    async def pause_command(client, message):
        await admin_action(client, message, "pause")

    @app.on_message(
        filters.command("resume") & filters.group
    )
    async def resume_command(client, message):
        await admin_action(client, message, "resume")

    @app.on_message(
        filters.regex(
            r"(?i)^/?(?:(?:adisha|baby)\s+)?skip$"
        )
        & filters.group
        & filters.text
    )
    async def skip_command(client, message):
        await admin_action(client, message, "skip")

    @app.on_message(
        filters.command("stop") & filters.group
    )
    async def stop_command(client, message):
        await admin_action(client, message, "stop")

    @app.on_message(
        filters.regex(
            rf"(?i)^(?:{TRIGGER})\s+(pause|resume|stop)$"
        )
        & filters.group
    )
    async def trigger_admin_command(client, message):
        match = (
            message.matches[0]
            if message.matches
            else None
        )

        if not match:
            return

        action = match.group(1).lower()

        await admin_action(
            client,
            message,
            action,
        )
