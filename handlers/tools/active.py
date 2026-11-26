from pyrogram import filters
from pyrogram.enums import ParseMode

from config import SUDO_USERS
from music import music_queue


def register_active_handlers(app):
    owner_filter = filters.user(list(SUDO_USERS))

    @app.on_message(filters.command(["active", "activevc", "activevoice"]) & owner_filter)
    async def active_voice_chats(client, message):
        status = await message.reply_text("🔎 Fetching active V3 Music voice chats...")
        chat_ids = await music_queue.get_active_chat_ids()

        if not chat_ids:
            return await status.edit_text("🎧 <b>No active voice chats right now.</b>", parse_mode=ParseMode.HTML)

        lines = []
        for index, chat_id in enumerate(chat_ids, start=1):
            try:
                chat = await client.get_chat(chat_id)
                title = chat.title or "Private chat"
                if chat.username:
                    title = f'<a href="https://t.me/{chat.username}">{title}</a>'
                lines.append(f"<b>{index}.</b> {title} <code>{chat_id}</code>")
            except Exception:
                lines.append(f"<b>{index}.</b> <code>{chat_id}</code>")

        text = (
            "🎧 <b>V3 MUSIC — ACTIVE VOICE CHATS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(lines)
            + f"\n\n<b>Total:</b> <code>{len(chat_ids)}</code>"
        )
        await status.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
