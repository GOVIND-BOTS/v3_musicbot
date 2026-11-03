# handlers/chatbot.py

import os
import random
import asyncio
import logging
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus, ChatAction
from pymongo import MongoClient

from config import MONGO_DB_URI, BOT_TOKEN

LOGGER = logging.getLogger(__name__)

# ==================== CONFIG ====================
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
# ================================================

# MongoDB connection
mongo = MongoClient(MONGO_DB_URI) if MONGO_DB_URI else None
vick_db = mongo["VickDb"]["Vick"] if mongo is not None else None
word_db = mongo["Word"]["WordDb"] if mongo is not None else None


async def is_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


def is_chatbot_enabled(chat_id: int) -> bool:
    """Returns True if chatbot is enabled in the group"""
    if vick_db is None:
        return False
    # If chat_id is present in DB → chatbot is OFF
    return not vick_db.find_one({"chat_id": chat_id})


def register_chatbot_handlers(app):

    # -------------------- /chatbot on/off --------------------
    @app.on_message(
        filters.command(["chatbot"], prefixes=["/", ".", "?", "-"]) & filters.group
    )
    async def chatbot_status(_, message: Message):
        if len(message.command) < 2:
            return await message.reply_text(
                "**Usage:**\n"
                "`/chatbot on` - Enable chatbot\n"
                "`/chatbot off` - Disable chatbot"
            )

        action = message.command[1].lower()

        if not await is_admin(_, message.chat.id, message.from_user.id):
            return await message.reply_text("Sirf admin ye command use kar sakte hain.")

        if action == "on":
            if is_chatbot_enabled(message.chat.id):
                return await message.reply_text("Chatbot already enabled hai!")
            vick_db.delete_one({"chat_id": message.chat.id})
            await message.reply_text("✅ Chatbot Enabled!")

        elif action == "off":
            if not is_chatbot_enabled(message.chat.id):
                return await message.reply_text("Chatbot already disabled hai!")
            vick_db.insert_one({"chat_id": message.chat.id})
            await message.reply_text("❌ Chatbot Disabled!")

        else:
            await message.reply_text("Sirf `on` ya `off` use karo.")

    # -------------------- Main Chat Handler (Group) --------------------
    @app.on_message(
        (filters.text | filters.sticker) & filters.group & ~filters.bot,
        group=2
    )
    async def group_chatbot(client, message: Message):
        if word_db is None or vick_db is None:
            return

        # Agar chatbot off hai to ignore
        if not is_chatbot_enabled(message.chat.id):
            return

        # Ignore commands
        if message.text and message.text.startswith(("/", ".", "?", "-")):
            return

        try:
            # Case 1: User ne kisi message pe reply nahi kiya
            if not message.reply_to_message:
                await client.send_chat_action(message.chat.id, ChatAction.TYPING)

                if message.text:
                    results = list(word_db.find({"word": message.text}))
                elif message.sticker:
                    results = list(word_db.find({"word": message.sticker.file_unique_id}))
                else:
                    return

                if not results:
                    return

                chosen = random.choice(results)
                response = chosen.get("text")
                check = chosen.get("check")

                if check == "sticker":
                    await message.reply_sticker(response)
                else:
                    await message.reply_text(response)

            # Case 2: User ne bot ke message pe reply kiya → Learn karo
            else:
                bot_me = await client.get_me()
                if message.reply_to_message.from_user.id != bot_me.id:
                    # User ne kisi aur ke message pe reply kiya → Save karo for learning
                    if message.text and message.reply_to_message.text:
                        exists = word_db.find_one({
                            "word": message.reply_to_message.text,
                            "text": message.text
                        })
                        if not exists:
                            word_db.insert_one({
                                "word": message.reply_to_message.text,
                                "text": message.text,
                                "check": "none"
                            })

                    elif message.sticker and message.reply_to_message.text:
                        exists = word_db.find_one({
                            "word": message.reply_to_message.text,
                            "id": message.sticker.file_unique_id
                        })
                        if not exists:
                            word_db.insert_one({
                                "word": message.reply_to_message.text,
                                "text": message.sticker.file_id,
                                "check": "sticker",
                                "id": message.sticker.file_unique_id
                            })
                else:
                    # Bot ke message pe reply kiya → Reply do
                    await client.send_chat_action(message.chat.id, ChatAction.TYPING)

                    if message.text:
                        results = list(word_db.find({"word": message.text}))
                    else:
                        return

                    if results:
                        chosen = random.choice(results)
                        response = chosen.get("text")
                        check = chosen.get("check")

                        if check == "sticker":
                            await message.reply_sticker(response)
                        else:
                            await message.reply_text(response)

        except Exception as e:
            LOGGER.exception(f"Chatbot error: {e}")

    # -------------------- Private Chat Support --------------------
    @app.on_message(
        (filters.text | filters.sticker) & filters.private & ~filters.bot
    )
    async def private_chatbot(client, message: Message):
        if word_db is None:
            return

        try:
            await client.send_chat_action(message.chat.id, ChatAction.TYPING)

            if message.text:
                results = list(word_db.find({"word": message.text}))
            elif message.sticker:
                results = list(word_db.find({"word": message.sticker.file_unique_id}))
            else:
                return

            if not results:
                return

            chosen = random.choice(results)
            response = chosen.get("text")
            check = chosen.get("check")

            if check == "sticker":
                await message.reply_sticker(response)
            else:
                await message.reply_text(response)

        except Exception as e:
            LOGGER.exception(f"Private chatbot error: {e}")

    LOGGER.info("Vick-style Chatbot handlers registered successfully.")
