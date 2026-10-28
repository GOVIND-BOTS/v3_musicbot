from pyrogram import filters
from music import music_queue
from buttons import queue_buttons

def register_callback_handlers(app, stream):
    @app.on_callback_query(filters.regex(r"^ctrl_"))
    async def player_controls(client, query):
        data = query.data or ""
        if data == "ctrl_close":
            await query.answer()
            try: await query.message.delete()
            except Exception: pass
            return
        parts = data.split("|")
        action = parts[0]
        chat_id = int(parts[1]) if len(parts) > 1 else query.message.chat.id
        if query.from_user and query.message.chat.type != "private" and query.from_user.id != chat_id:
            # Any group member can control playback for now.
            pass
        try:
            if action == "ctrl_queue":
                items = await music_queue.get_queue(chat_id)
                current = await music_queue.get_current(chat_id)
                text = "**🎶 Queue**\n"
                if current: text += f"\n▶️ Current: {current.get('title','Unknown')}\n"
                if not items: text += "\nQueue is empty."
                else:
                    text += "\n" + "\n".join(f"{i}. {t.get('title','Unknown')}" for i, t in enumerate(items, 1))
                await query.answer()
                await query.message.reply_text(text, reply_markup=queue_buttons(chat_id))
                return
            if action == "ctrl_pause":
                await stream.pause(chat_id)
                answer = "Paused"
            elif action == "ctrl_resume":
                await stream.resume(chat_id)
                answer = "Resumed"
            elif action == "ctrl_skip":
                track = await stream.skip(chat_id)
                answer = f"Skipped. {track.get('title','Next track playing')}" if track else "Queue finished."
            elif action == "ctrl_stop":
                await stream.stop(chat_id)
                answer = "Stopped"
            elif action == "ctrl_replay":
                track = await stream.replay(chat_id)
                answer = "Replaying current track" if track else "Nothing is playing"
            else:
                answer = "Unknown control"
            await query.answer(answer)
        except Exception as exc:
            await query.answer(f"Action failed: {type(exc).__name__}", show_alert=True)
