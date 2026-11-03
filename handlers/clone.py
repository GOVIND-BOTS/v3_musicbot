
import logging

from pyrogram import filters, Client
from pyrogram.types import Message
from pyrogram.errors import ApiIdInvalid, AccessTokenInvalid

from config import API_ID, API_HASH
from database.clone_db import save_clone, is_token_exist

LOGGER = logging.getLogger(__name__)

# Temporary storage for users currently in the cloning process
clone_waiting = {}


def register_clone_handlers(app):

    @app.on_message(filters.command("clone") & filters.private)
    async def clone_command(client, message: Message):
        user_id = message.from_user.id
        clone_waiting[user_id] = True

        await message.reply_text(
            "🤖 **Bot Cloning System**\n\n"
            "Please send your **Bot Token**.\n\n"
            "Example:\n"
            "`1234567890:AAHxxxx...`\n\n"
            "You can get your bot token from @BotFather.",
            quote=True
        )

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command(["start", "clone", "help"])
    )
    async def receive_token(client, message: Message):
        user_id = message.from_user.id

        if user_id not in clone_waiting:
            return

        token = message.text.strip()

        if ":" not in token or len(token) < 40:
            await message.reply_text(
                "❌ Invalid token format. Please send a valid bot token."
            )
            return

        # Check if the token has already been cloned
        if await is_token_exist(token):
            await message.reply_text(
                "⚠️ This bot token has already been cloned."
            )
            del clone_waiting[user_id]
            return

        status = await message.reply_text(
            "⏳ Validating your bot token..."
        )

        temp_client = None

        try:
            # Validate the bot token using a temporary client
            temp_client = Client(
                "temp_clone_check",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=token,
                in_memory=True
            )

            await temp_client.start()
            me = await temp_client.get_me()

            await temp_client.stop()
            temp_client = None

            # Save the cloned bot to the database
            await save_clone(
                owner_id=user_id,
                bot_token=token,
                bot_username=me.username
            )

            await status.edit_text(
                f"✅ **Bot Cloned Successfully!**\n\n"
                f"🤖 **Bot:** @{me.username}\n"
                f"👤 **Owner ID:** `{user_id}`\n\n"
                "Your cloned bot has been saved successfully.\n"
                "It will start automatically after a restart, "
                "provided your hosting environment supports "
                "multiple bot instances."
            )

        except AccessTokenInvalid:
            await status.edit_text(
                "❌ Invalid Bot Token. Please generate a new token "
                "using @BotFather."
            )

        except Exception as e:
            LOGGER.exception("Clone failed")

            await status.edit_text(
                f"❌ **Cloning Failed!**\n\n"
                f"Error: `{str(e)[:200]}`"
            )

        finally:
            if temp_client is not None:
                try:
                    await temp_client.stop()
                except Exception:
                    pass

            clone_waiting.pop(user_id, None)
