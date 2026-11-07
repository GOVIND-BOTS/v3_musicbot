
import os
import random
import logging

from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus, ChatAction
from pymongo import MongoClient

from config import MONGO_DB_URI

LOGGER = logging.getLogger(__name__)

BOT_USERNAME = os.getenv("BOT_USERNAME", "")

mongo = MongoClient(MONGO_DB_URI) if MONGO_DB_URI else None
vick_db = mongo["VickDb"]["Vick"] if mongo is not None else None
word_db = mongo["Word"]["WordDb"] if mongo is not None else None

PRIVATE_EXCLUDED_COMMANDS = [
    "eval",
    "test",
    "start",
    "help",
    "clone",
    "clones",
    "cancel",
    "removeclone",
]


async def is_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR
        )
    except Exception:
        return False


def is_chatbot_enabled(chat_id: int) -> bool:
    if vick_db is None:
        return False

    return not vick_db.find_one({"chat_id": chat_id})


def register_chatbot_handlers(app):

    @app.on_message(
        filters.command(
            ["chatbot"],
            prefixes=["/", ".", "?", "-"]
        ) & filters.group
    )
    async def chatbot_status(client, message: Message):

        if len(message.command) < 2:
            return await message.reply_text(
                "**Usage:**\n"
                "`/chatbot on` - Enable chatbot\n"
                "`/chatbot off` - Disable chatbot"
            )

        if not message.from_user:
            return

        action = message.command[1].lower()

        if not await is_admin(
            client,
            message.chat.id,
            message.from_user.id
        ):
            return await message.reply_text(
                "Sirf admin ye command use kar sakte hain."
            )

        if vick_db is None:
            return await message.reply_text(
                "Chatbot database unavailable."
            )

        if action == "on":
            if is_chatbot_enabled(message.chat.id):
                return await message.reply_text(
                    "Chatbot already enabled hai!"
                )

            vick_db.delete_one({"chat_id": message.chat.id})
            await message.reply_text("✅ Chatbot Enabled!")

        elif action == "off":
            if not is_chatbot_enabled(message.chat.id):
                return await message.reply_text(
                    "Chatbot already disabled hai!"
                )

            vick_db.insert_one({"chat_id": message.chat.id})
            await message.reply_text("❌ Chatbot Disabled!")

        else:
            await message.reply_text(
                "Sirf `on` ya `off` use karo."
            )

    # Group chatbot
    @app.on_message(
        (filters.text | filters.sticker)
        & filters.group
        & ~filters.bot
        & ~filters.command(
            ["chatbot"],
            prefixes=["/", ".", "?", "-"]
        ),
        group=2
    )
    async def group_chatbot(client, message: Message):

        if word_db is None or vick_db is None:
            return

        if not is_chatbot_enabled(message.chat.id):
            return

        if message.text and message.text.startswith(
            ("/", ".", "?", "-")
        ):
            return

        try:
            if not message.reply_to_message:

                await client.send_chat_action(
                    message.chat.id,
                    ChatAction.TYPING
                )

                if message.text:
                    results = list(
                        word_db.find({"word": message.text})
                    )
                elif message.sticker:
                    results = list(
                        word_db.find({
                            "word": message.sticker.file_unique_id
                        })
                    )
                else:
                    return

                if not results:
                    return

                chosen = random.choice(results)

                if chosen.get("check") == "sticker":
                    await message.reply_sticker(chosen.get("text"))
                else:
                    await message.reply_text(chosen.get("text"))

            else:
                bot_me = await client.get_me()

                if (
                    not message.reply_to_message.from_user
                    or message.reply_to_message.from_user.id != bot_me.id
                ):

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

                    elif (
                        message.sticker
                        and message.reply_to_message.text
                    ):
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
                    await client.send_chat_action(
                        message.chat.id,
                        ChatAction.TYPING
                    )

                    if not message.text:
                        return

                    results = list(
                        word_db.find({"word": message.text})
                    )

                    if results:
                        chosen = random.choice(results)

                        if chosen.get("check") == "sticker":
                            await message.reply_sticker(
                                chosen.get("text")
                            )
                        else:
                            await message.reply_text(
                                chosen.get("text")
                            )

        except Exception:
            LOGGER.exception("Chatbot group error")

    # Private chatbot
    @app.on_message(
        (filters.text | filters.sticker)
        & filters.private
        & ~filters.bot
        & ~filters.command(
            PRIVATE_EXCLUDED_COMMANDS,
            prefixes=["/", ".", "?", "-"]
        ),
        group=2
    )
    async def private_chatbot(client, message: Message):

        if word_db is None:
            return

        if message.text and message.text.startswith(
            ("/", ".", "?", "-")
        ):
            return

        try:
            await client.send_chat_action(
                message.chat.id,
                ChatAction.TYPING
            )

            if message.text:
                results = list(
                    word_db.find({"word": message.text})
                )
            elif message.sticker:
                results = list(
                    word_db.find({
                        "word": message.sticker.file_unique_id
                    })
                )
            else:
                return

            if not results:
                return

            chosen = random.choice(results)

            if chosen.get("check") == "sticker":
                await message.reply_sticker(chosen.get("text"))
            else:
                await message.reply_text(chosen.get("text"))

        except Exception:
            LOGGER.exception("Chatbot private error")

    LOGGER.info(
        "Vick-style Chatbot handlers registered successfully."
    )
