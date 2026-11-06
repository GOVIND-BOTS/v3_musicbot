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
    get_clones_by_owner,
    remove_clone,
)
from clone_manager import clone_manager

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
    for uid in users:
        try:
            result.add(int(uid))
        except (TypeError, ValueError):
            continue
    return result


def is_clone_admin(user_id: int) -> bool:
    try:
        return int(user_id) in get_allowed_users()
    except Exception:
        return False


def register_clone_handlers(app):
    @app.on_message(filters.command("clone") & filters.private)
    async def clone_command(client, message: Message):
        if not message.from_user:
            return

        user_id = message.from_user.id
        if not is_clone_admin(user_id):
            return await message.reply_text("❌ You are not authorized to use this command.")

        count = await count_active_clones()
        if count >= MAX_CLONES:
            return await message.reply_text(
                f"❌ Maximum clone limit reached ({MAX_CLONES})."
            )

        clone_waiting[user_id] = True
        await message.reply_text(
            "🤖 **BOT CLONING SYSTEM**\n\n"
            "Please send your Bot Token.\n\n"
            "Use /cancel to cancel."
        )

    @app.on_message(filters.command("cancel") & filters.private)
    async def cancel_clone(client, message: Message):
        if not message.from_user:
            return
        user_id = message.from_user.id
        if user_id in clone_waiting:
            clone_waiting.pop(user_id, None)
            await message.reply_text("❌ Clone process cancelled.")

    @app.on_message(filters.command("clones") & filters.private)
    async def list_clones(client, message: Message):
        if not message.from_user or not is_clone_admin(message.from_user.id):
            return await message.reply_text("❌ Owner/Sudo only.")

        clones = await get_clones_by_owner(message.from_user.id)
        if not clones:
            return await message.reply_text("No active clones found.")

        lines = [f"**Active Clones ({len(clones)}/{MAX_CLONES}):**\n"]
        for i, c in enumerate(clones, 1):
            uname = c.get("bot_username") or "Unknown"
            lines.append(f"{i}. @{uname}")
        await message.reply_text("\n".join(lines))

    @app.on_message(filters.command("removeclone") & filters.private)
    async def remove_clone_cmd(client, message: Message):
        if not message.from_user or not is_clone_admin(message.from_user.id):
            return await message.reply_text("❌ Owner/Sudo only.")

        parts = (message.text or "").split(None, 1)
        if len(parts) < 2:
            return await message.reply_text(
                "Usage:\n`/removeclone bot_username`"
            )

        query = parts[1].strip().lstrip("@")
        clones = await get_clones_by_owner(message.from_user.id)
        target = None
        for c in clones:
            if (c.get("bot_username") or "").lower() == query.lower():
                target = c
                break

        if not target:
            return await message.reply_text("Clone not found.")

        token = target["bot_token"]
        await clone_manager.stop_clone(token)
        await remove_clone(token)
        await message.reply_text(
            f"✅ Clone removed: @{target.get('bot_username')}"
        )

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command(
            ["start", "clone", "help", "cancel", "clones", "removeclone"]
        )
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
            return await message.reply_text("❌ Invalid token format.")

        if await is_token_exist(token):
            clone_waiting.pop(user_id, None)
            return await message.reply_text(
                "⚠️ This bot token is already registered."
            )

        count = await count_active_clones()
        if count >= MAX_CLONES:
            clone_waiting.pop(user_id, None)
            return await message.reply_text(
                f"❌ Maximum clone limit reached ({MAX_CLONES})."
            )

        status = await message.reply_text("⏳ Validating your bot token...")
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
                return await status.edit_text(
                    "❌ Could not save clone (limit or duplicate)."
                )

            clone_saved = True

            started = await clone_manager.start_clone(
                {
                    "owner_id": user_id,
                    "bot_token": token,
                    "bot_username": me.username,
                }
            )

            if started:
                await status.edit_text(
                    "✅ **BOT CLONED SUCCESSFULLY!**\n\n"
                    f"🤖 Bot: @{me.username or 'Unknown'}\n"
                    f"👤 Owner ID: `{user_id}`\n\n"
                    "Your clone is now online."
                )
            else:
                await status.edit_text(
                    "✅ Bot token validated and saved.\n\n"
                    "⚠️ The clone could not start right now.\n"
                    "It will be retried when the main bot restarts."
                )

        except AccessTokenInvalid:
            await status.edit_text(
                "❌ Invalid Bot Token. Generate a new one from BotFather."
            )
        except Exception:
            LOGGER.exception("Clone operation failed.")
            if clone_saved:
                await status.edit_text(
                    "⚠️ Clone was saved, but startup failed. Check server logs."
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
                    pass
            clone_waiting.pop(user_id, None)
