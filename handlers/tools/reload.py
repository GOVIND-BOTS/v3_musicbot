import time

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode

from config import SUDO_USERS


_LAST_RELOAD = {}


def register_reload_handlers(app):
    @app.on_message(filters.command(["reload", "refresh", "admincache"]) & filters.group)
    async def reload_group(client, message):
        user = message.from_user
        if not user:
            return

        if user.id not in SUDO_USERS:
            try:
                member = await client.get_chat_member(message.chat.id, user.id)
                if member.status not in (
                    ChatMemberStatus.OWNER,
                    ChatMemberStatus.ADMINISTRATOR,
                ):
                    return await message.reply_text("❌ Only group admins can use /reload.")
            except Exception:
                return await message.reply_text("❌ I could not verify your admin permissions.")

        chat_id = message.chat.id
        now = time.monotonic()
        previous = _LAST_RELOAD.get(chat_id, 0)

        if now - previous < 15:
            remaining = int(15 - (now - previous))
            return await message.reply_text(
                f"⏳ Please wait {remaining}s before refreshing this group again."
            )

        status = await message.reply_text("🔄 Refreshing group information...")

        try:
            chat = await client.get_chat(chat_id)
            me = await client.get_me()
            bot_member = await client.get_chat_member(chat_id, me.id)

            if bot_member.status not in (
                ChatMemberStatus.OWNER,
                ChatMemberStatus.ADMINISTRATOR,
            ):
                return await status.edit_text(
                    "⚠️ V3 Music is not an administrator in this group. "
                    "Some music features may not work."
                )

            _LAST_RELOAD[chat_id] = now
            await status.edit_text(
                "✅ <b>Group refresh completed.</b>\n\n"
                f"📌 <b>Group:</b> {chat.title or chat_id}\n"
                f"🤖 <b>Bot role:</b> <code>{bot_member.status.value}</code>\n"
                "🎧 <b>Playback:</b> Unchanged\n"
                "ℹ️ This refresh checks the current Telegram group and bot permissions. "
                "It does not restart the Railway service or interrupt music.",
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            await status.edit_text(
                f"❌ Refresh failed: <code>{type(exc).__name__}</code>",
                parse_mode=ParseMode.HTML,
            )
