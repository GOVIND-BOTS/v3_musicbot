from pyrogram import filters
from pyrogram.types import CallbackQuery
from config import START_IMAGE, SUPPORT_CHANNEL, SUPPORT_CHAT, OWNER_ID, BOT_NAME
from buttons import start_buttons, help_buttons
from database.mongodb import add_user

START_TEXT = (
    f"🎧 **Welcome to {BOT_NAME}!**\n\n"
    "I can play music in your group's voice chat.\n\n"
    "Use `/play song name` to search and play music.\n"
    "Use `/vplay song name` to play video in voice chat.\n"
    "Use `/queue` to see upcoming tracks and `/help` for commands."
)
HELP_TEXT = (
    "**🎧 Music Bot Help**\n\n"
    "`/play <song or YouTube link>` — search/play audio\n"
    "`/vplay <song or YouTube link>` — video stream\n"
    "`/queue` — show upcoming tracks\n"
    "`/now` — show current track\n"
    "`/pause`, `/resume`, `/skip`, `/stop` — playback controls\n"
    "`/clearqueue` — clear queue"
)

def register_start_handlers(app):
    @app.on_message(filters.command("start") & filters.private)
    async def start_command(client, message):
        if message.from_user:
            try: await add_user(message.from_user.id)
            except Exception: pass
        me = await client.get_me()
        markup = start_buttons(OWNER_ID, SUPPORT_CHAT, SUPPORT_CHANNEL, me.username or "")
        if START_IMAGE:
            try:
                await message.reply_photo(START_IMAGE, caption=START_TEXT, reply_markup=markup)
                return
            except Exception:
                pass
        await message.reply_text(START_TEXT, reply_markup=markup, disable_web_page_preview=True)

    @app.on_message(filters.command("help"))
    async def help_command(client, message):
        await message.reply_text(HELP_TEXT, reply_markup=help_buttons())

    @app.on_callback_query(filters.regex("^help_cmd$"))
    async def help_callback(client, query: CallbackQuery):
        await query.answer()
        await query.message.edit_text(HELP_TEXT, reply_markup=help_buttons())

    @app.on_callback_query(filters.regex("^start_home$"))
    async def home_callback(client, query: CallbackQuery):
        await query.answer()
        me = await client.get_me()
        markup = start_buttons(OWNER_ID, SUPPORT_CHAT, SUPPORT_CHANNEL, me.username or "")
        try:
            await query.message.edit_text(START_TEXT, reply_markup=markup)
        except Exception:
            await query.message.reply_text(START_TEXT, reply_markup=markup)
