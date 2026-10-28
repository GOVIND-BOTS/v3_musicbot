from pyrogram import filters
from music import music_queue

def register_queue_handlers(app, stream):
    @app.on_message(filters.command("queue") & filters.group)
    async def queue_command(client, message):
        current = await music_queue.get_current(message.chat.id)
        items = await music_queue.get_queue(message.chat.id)
        lines = ["**🎶 Music Queue**"]
        if current:
            lines.append(f"\n▶️ **Now playing:** {current.get('title','Unknown')}")
        if items:
            lines.extend(f"{i}. {item.get('title','Unknown')}" for i, item in enumerate(items, 1))
        elif not current:
            lines.append("Queue is empty.")
        await message.reply_text("\n".join(lines))

    @app.on_message(filters.command("now") & filters.group)
    async def now_command(client, message):
        current = await music_queue.get_current(message.chat.id)
        if not current:
            await message.reply_text("Nothing is playing right now.")
            return
        await message.reply_text(f"🎶 **Now Playing**\n{current.get('title','Unknown')}\nDuration: {current.get('duration_text','?')}")

    @app.on_message(filters.command("clearqueue") & filters.group)
    async def clearqueue_command(client, message):
        await music_queue.clear(message.chat.id)
        try:
            await stream.stop(message.chat.id)
        except Exception:
            pass
        await message.reply_text("Queue cleared and playback stopped.")
