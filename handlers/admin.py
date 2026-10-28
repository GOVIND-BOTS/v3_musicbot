from pyrogram import filters
from pyrogram.enums import ChatMemberStatus

async def _is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False

def register_admin_handlers(app, stream):
    async def admin_action(client, message, action):
        if not message.from_user or not await _is_admin(client, message.chat.id, message.from_user.id):
            await message.reply_text("Only group admins can use this command.")
            return
        try:
            if action == "pause":
                await stream.pause(message.chat.id)
                text = "Playback paused."
            elif action == "resume":
                await stream.resume(message.chat.id)
                text = "Playback resumed."
            elif action == "skip":
                track = await stream.skip(message.chat.id)
                text = f"Skipped. Now playing: {track.get('title','next track')}" if track else "Queue finished."
            else:
                await stream.stop(message.chat.id)
                text = "Playback stopped and queue cleared."
            await message.reply_text(text)
        except Exception as exc:
            await message.reply_text(f"Command failed: `{type(exc).__name__}`")

    @app.on_message(filters.command("pause") & filters.group)
    async def pause_command(client, message): await admin_action(client, message, "pause")

    @app.on_message(filters.command("resume") & filters.group)
    async def resume_command(client, message): await admin_action(client, message, "resume")

    @app.on_message(filters.command("skip") & filters.group)
    async def skip_command(client, message): await admin_action(client, message, "skip")

    @app.on_message(filters.command("stop") & filters.group)
    async def stop_command(client, message): await admin_action(client, message, "stop")
