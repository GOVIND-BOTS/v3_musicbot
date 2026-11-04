import logging

from pyrogram import filters, Client
from pyrogram.types import Message
from pyrogram.errors import AccessTokenInvalid

from config import API_ID, API_HASH, OWNER_ID, SUDO_USERS

from database.clone_db import (
    save_clone,
    is_token_exist,
    MAX_CLONES,
    count_active_clones,
)

LOGGER = logging.getLogger(__name__)

clone_waiting = {}


def get_allowed_users():
    users = set()

    if isinstance(OWNER_ID, (list, tuple, set)):
        users.update(OWNER_ID)
    elif OWNER_ID:
        users.add(OWNER_ID)

    if isinstance(SUDO_USERS, (list, tuple, set)):
        users.update(SUDO_USERS)
    elif SUDO_USERS:
        users.add(SUDO_USERS)

    result = set()

    for user_id in users:
        try:
            result.add(int(user_id))
        except (TypeError, ValueError):
            continue

    return result


def is_clone_admin(user_id):
    return user_id in get_allowed_users()


def register_clone_handlers(app):

    @app.on_message(
        filters.command("clone") & filters.private
    )
    async def clone_command(client, message: Message):

        if not message.from_user:
            return

        user_id = message.from_user.id

        if not is_clone_admin(user_id):
            await message.reply_text(
                "❌ You are not authorized to use this command."
            )
            return

        count = await count_active_clones()

        if count >= MAX_CLONES:
            await message.reply_text(
                f"❌ Maximum clone limit reached ({MAX_CLONES})."
            )
            return

        clone_waiting[user_id] = True

        await message.reply_text(
            "🤖 BOT CLONING SYSTEM\n\n"
            "Please send your Bot Token.\n\n"
            "Use /cancel to cancel this process."
        )

    @app.on_message(
        filters.command("cancel") & filters.private
    )
    async def cancel_clone(client, message: Message):

        if not message.from_user:
            return

        user_id = message.from_user.id

        if user_id in clone_waiting:
            clone_waiting.pop(user_id, None)

            await message.reply_text(
                "❌ Clone process cancelled."
            )

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command([
            "start",
            "clone",
            "help",
            "cancel",
        ])
    )
    async def receive_token(client, message: Message):

        if not message.from_user:
            return

        user_id = message.from_user.id

        if user_id not in clone_waiting:
            return

        if not is_clone_admin(user_id):
            clone_waiting.pop(user_id, None)
            return

        token = (message.text or "").strip()

        if ":" not in token or len(token) < 40:
            await message.reply_text(
                "❌ Invalid token format. Please send a valid token."
            )
            return

        if await is_token_exist(token):
            clone_waiting.pop(user_id, None)

            await message.reply_text(
                "⚠️ This bot token has already been registered."
            )
            return

        count = await count_active_clones()

        if count >= MAX_CLONES:
            clone_waiting.pop(user_id, None)

            await message.reply_text(
                f"❌ Maximum clone limit reached ({MAX_CLONES})."
            )
            return

        status = await message.reply_text(
            "⏳ Validating your bot token..."
        )

        temp_client = None
        clone_saved = False

        try:
            temp_client = Client(
                f"clone_check_{user_id}",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=token,
                in_memory=True,
            )

            await temp_client.start()

            me = await temp_client.get_me()

            await temp_client.stop()
            temp_client = None

            saved = await save_clone(
                owner_id=user_id,
                bot_token=token,
                bot_username=me.username,
            )

            if not saved:
                await status.edit_text(
                    "❌ Clone limit reached or token already exists."
                )
                return

            clone_saved = True

            # Start the clone immediately using the shared stream.
            from clone_manager import clone_manager

            started = await clone_manager.start_clone({
                "owner_id": user_id,
                "bot_token": token,
                "bot_username": me.username,
            })

            if started:
                await status.edit_text(
                    "✅ BOT CLONED SUCCESSFULLY!\n\n"
                    f"🤖 Bot: @{me.username or 'Unknown'}\n"
                    f"👤 Owner ID: {user_id}\n\n"
                    "Your clone is now online."
                )
            else:
                await status.edit_text(
                    "✅ Bot token validated and saved.\n\n"
                    "⚠️ The clone could not start right now. "
                    "It will be retried when the main bot restarts."
                )

        except AccessTokenInvalid:
            await status.edit_text(
                "❌ Invalid Bot Token. Generate a new token using BotFather."
            )

        except Exception:
            LOGGER.exception("Clone operation failed.")

            if clone_saved:
                await status.edit_text(
                    "⚠️ Clone was saved, but startup failed. "
                    "Check the server logs."
                )
            else:
                await status.edit_text(
                    "❌ Cloning failed. Please check the server logs."
                )

        finally:
            if temp_client is not None:
                try:
                    if temp_client.is_connected:
                        await temp_client.stop()
                except Exception:
                    LOGGER.exception("Temporary client cleanup failed.")

            clone_waiting.pop(user_id, None)
