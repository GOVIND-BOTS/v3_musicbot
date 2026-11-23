from pyrogram import filters
from pyrogram.enums import ParseMode

from owner_manager import get_public_owner, is_main_owner, set_public_owner
from player_ui import stylize


def register_owner_control_handlers(app):
    @app.on_message(filters.command("setowner"))
    async def set_owner_command(client, message):
        if not message.from_user or not is_main_owner(message.from_user.id):
            await message.reply_text(stylize("Only the main owner can change the public owner profile."))
            return

        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text(
                "<b>Owner profile settings</b>\n"
                "<code>/setowner @username</code>\n"
                "<code>/setowner 123456789</code>\n"
                "<code>/setowner default</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        try:
            profile = await set_public_owner(parts[1])
        except ValueError as error:
            await message.reply_text(str(error))
            return
        label = f"@{profile['username']}" if profile["username"] else str(profile["user_id"])
        await message.reply_text(f"✅ Public owner button updated: <b>{label}</b>", parse_mode=ParseMode.HTML)

    @app.on_message(filters.command("owner"))
    async def owner_profile_command(client, message):
        profile = await get_public_owner()
        label = f"@{profile['username']}" if profile["username"] else str(profile["user_id"])
        await message.reply_text(f"👑 Public owner: <b>{label}</b>", parse_mode=ParseMode.HTML)
