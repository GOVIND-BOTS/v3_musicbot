import os
import re
import logging
from datetime import datetime, timedelta, timezone
from html import escape

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatPermissions,
)

from database.anti_abuse_db import (
    get_chat_settings,
    update_chat_settings,
    add_banned_word,
    remove_banned_word,
    add_warning,
    get_warnings,
    reset_warnings,
)

LOGGER = logging.getLogger(__name__)

WARNING_LIMIT = 3
DEFAULT_MUTE_SECONDS = 3600

# Basic default filter words. Group admins can add more with /galiadd.
DEFAULT_BANNED_WORDS = [
    "chutiya",
    "mc",
    "bc",
    "bhenchod",
    "madarchod",
    "gaand",
]

IMAGE_PATH = "assets/anti_abuse.png"


def contains_abuse(text, custom_words):
    words = set(DEFAULT_BANNED_WORDS + custom_words)

    for word in words:
        word = word.strip().lower()

        if not word:
            continue

        pattern = r"(?<!\w)" + re.escape(word) + r"(?!\w)"

        if re.search(pattern, text, flags=re.IGNORECASE):
            return True

    return False


async def is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)

        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


async def show_settings(message, settings):
    status = "🟢 ENABLED" if settings["enabled"] else "🔴 DISABLED"

    text = (
        "🍃ᶦϻᷧ) <b>V3 MUSIC</b> 🍃\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🛡️ <b>𝐀ɴᴛɪ-𝐀ʙᴜsᴇ 𝐏ᴀɴᴇʟ</b>\n\n"
        f"⚙️ Status: <b>{status}</b>\n"
        f"⚠️ Warning Limit: <b>{WARNING_LIMIT}</b>\n"
        f"🔇 Mute Duration: <b>{settings['mute_seconds'] // 60} minutes</b>\n"
        f"🚫 Custom Words: <b>{len(settings.get('banned_words', []))}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🍃 <i>Keep your group respectful!</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🟢 Enable",
                callback_data="ab:enable",
            ),
            InlineKeyboardButton(
                "🔴 Disable",
                callback_data="ab:disable",
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 My Warnings",
                callback_data="ab:mywarn",
            ),
            InlineKeyboardButton(
                "📜 Group Policy",
                callback_data="ab:policy",
            ),
        ],
        [
            InlineKeyboardButton(
                "❌ Close",
                callback_data="ab:close",
            ),
        ],
    ])

    await message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )


def register_anti_abuse_handlers(app):

    @app.on_message(filters.command("antigali") & filters.group)
    async def anti_gali_panel(client, message):
        if not message.from_user:
            return

        if not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text(
                "❌ Only group admins can manage Anti-Abuse."
            )

        settings = await get_chat_settings(message.chat.id)
        await show_settings(message, settings)

    @app.on_message(filters.command("galiadd") & filters.group)
    async def add_word(client, message):
        if not message.from_user:
            return

        if not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text("❌ Admin only command.")

        if len(message.command) < 2:
            return await message.reply_text(
                "Usage: <code>/galiadd word</code>",
                parse_mode=ParseMode.HTML,
            )

        word = " ".join(message.command[1:]).strip().lower()

        if len(word) > 40:
            return await message.reply_text("❌ Word is too long.")

        await add_banned_word(message.chat.id, word)

        await message.reply_text(
            f"✅ <b>Word added successfully!</b>\n\n"
            f"🚫 Word: <code>{escape(word)}</code>",
            parse_mode=ParseMode.HTML,
        )

    @app.on_message(filters.command("galidel") & filters.group)
    async def delete_word(client, message):
        if not message.from_user:
            return

        if not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text("❌ Admin only command.")

        if len(message.command) < 2:
            return await message.reply_text(
                "Usage: <code>/galidel word</code>",
                parse_mode=ParseMode.HTML,
            )

        word = " ".join(message.command[1:]).strip().lower()
        await remove_banned_word(message.chat.id, word)

        await message.reply_text(
            f"✅ <b>Word removed:</b> <code>{escape(word)}</code>",
            parse_mode=ParseMode.HTML,
        )

    @app.on_message(filters.command("galiwords") & filters.group)
    async def list_words(client, message):
        if not message.from_user:
            return

        if not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text("❌ Admin only command.")

        settings = await get_chat_settings(message.chat.id)
        words = settings.get("banned_words", [])

        text = (
            "🍃ᶦϻᷧ) <b>V3 MUSIC</b> 🍃\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🚫 <b>𝐂ᴜsᴛᴏᴍ 𝐅ɪʟᴛᴇʀ 𝐖ᴏʀᴅs</b>\n\n"
        )

        if words:
            text += "\n".join(
                f"• <code>{escape(word)}</code>" for word in words
            )
        else:
            text += "No custom words added."

        await message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
        )

    @app.on_message(filters.command("resetwarn") & filters.group)
    async def reset_user_warnings(client, message):
        if not message.from_user:
            return

        if not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text("❌ Admin only command.")

        target = message.reply_to_message.from_user if (
            message.reply_to_message
        ) else None

        if not target and len(message.command) > 1:
            try:
                target_id = int(message.command[1])
            except ValueError:
                return await message.reply_text("❌ Invalid user ID.")
        elif target:
            target_id = target.id
        else:
            return await message.reply_text(
                "Reply to a user or use /resetwarn USER_ID"
            )

        await reset_warnings(message.chat.id, target_id)

        await message.reply_text(
            f"✅ Warnings reset for <code>{target_id}</code>",
            parse_mode=ParseMode.HTML,
        )

    @app.on_message(filters.group & filters.text, group=20)
    async def anti_abuse_filter(client, message):
        if not message.from_user or message.from_user.is_bot:
            return

        settings = await get_chat_settings(message.chat.id)

        if not settings.get("enabled", False):
            return

        user_id = message.from_user.id

        # Group admins are exempt.
        if await is_admin(client, message.chat.id, user_id):
            return

        if not contains_abuse(
            message.text or "",
            settings.get("banned_words", []),
        ):
            return

        try:
            await message.delete()
        except Exception as error:
            LOGGER.warning("Could not delete abusive message: %s", error)

        warnings = await add_warning(message.chat.id, user_id)
        username = escape(message.from_user.first_name or "User")

        if warnings >= WARNING_LIMIT:
            mute_seconds = settings.get(
                "mute_seconds",
                DEFAULT_MUTE_SECONDS,
            )

            try:
                await client.restrict_chat_member(
                    message.chat.id,
                    user_id,
                    permissions=ChatPermissions(
                        can_send_messages=False,
                    ),
                    until_date=datetime.now(timezone.utc)
                    + timedelta(seconds=mute_seconds),
                )

                action_text = (
                    f"🔇 <b>Action:</b> Muted for "
                    f"<b>{mute_seconds // 60} minutes</b>"
                )

            except Exception as error:
                LOGGER.warning("Could not mute user: %s", error)
                action_text = (
                    "⚠️ <b>Mute failed.</b> Please check bot admin permissions."
                )
        else:
            action_text = (
                f"⚠️ <b>Warnings:</b> {warnings}/{WARNING_LIMIT}\n"
                f"🔇 <b>Next action:</b> Temporary mute"
            )

        caption = (
            "🍃ᶦϻᷧ) <b>V3 MUSIC</b> 🍃\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🛡️ <b>𝐆ʀᴏᴜᴘ 𝐏ʀᴏᴛᴇᴄᴛɪᴏɴ 𝐀ʟᴇʀᴛ</b>\n\n"
            "⚠️ <b>Abusive language detected!</b>\n\n"
            f"👤 <b>User:</b> {username}\n"
            f"📊 <b>Warning:</b> {warnings}/{WARNING_LIMIT}\n"
            f"{action_text}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🍃 <i>Please keep the group respectful!</i>\n"
            "🎧 <b>Enjoy Music, Not Abuse!</b>"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🛡️ Group Policy",
                    callback_data=f"ab:policy:{user_id}",
                ),
                InlineKeyboardButton(
                    "📊 User Warnings",
                    callback_data=f"ab:warnings:{user_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚙️ Anti Gali Settings",
                    callback_data="ab:settings",
                ),
                InlineKeyboardButton(
                    "🎧 Need Help?",
                    callback_data="ab:help",
                ),
            ],
        ])

        try:
            if os.path.exists(IMAGE_PATH):
                await message.reply_photo(
                    photo=IMAGE_PATH,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                )
            else:
                await message.reply_text(
                    caption,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                )
        except Exception as error:
            LOGGER.warning("Could not send moderation alert: %s", error)

    @app.on_callback_query(filters.regex(r"^ab:"))
    async def anti_abuse_callbacks(client, query):
        data = query.data.split(":")
        action = data[1]
        chat_id = query.message.chat.id
        user_id = query.from_user.id

        if action in ("enable", "disable", "settings"):
            if not await is_admin(client, chat_id, user_id):
                return await query.answer(
                    "Only group admins can do this!",
                    show_alert=True,
                )

        if action == "enable":
            await update_chat_settings(
                chat_id,
                {"enabled": True},
            )
            settings = await get_chat_settings(chat_id)
            await query.message.edit_text(
                "🟢 <b>Anti-Abuse Enabled!</b>\n\n"
                "V3 MUSIC is now protecting this group.",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "⚙️ Open Settings",
                            callback_data="ab:settings",
                        )
                    ]
                ]),
                parse_mode=ParseMode.HTML,
            )

        elif action == "disable":
            await update_chat_settings(
                chat_id,
                {"enabled": False},
            )
            await query.message.edit_text(
                "🔴 <b>Anti-Abuse Disabled!</b>",
                parse_mode=ParseMode.HTML,
            )

        elif action == "settings":
            if not await is_admin(client, chat_id, user_id):
                return await query.answer(
                    "Admin only!",
                    show_alert=True,
                )

            settings = await get_chat_settings(chat_id)
            status = "🟢 ENABLED" if settings["enabled"] else "🔴 DISABLED"

            await query.message.edit_text(
                "🍃ᶦϻᷧ) <b>V3 MUSIC</b> 🍃\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🛡️ <b>𝐀ɴᴛɪ-𝐀ʙᴜsᴇ 𝐒ᴇᴛᴛɪɴɢs</b>\n\n"
                f"Status: <b>{status}</b>\n"
                f"Mute: <b>{settings['mute_seconds'] // 60} minutes</b>\n"
                f"Custom words: <b>{len(settings.get('banned_words', []))}</b>",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🟢 Enable",
                            callback_data="ab:enable",
                        ),
                        InlineKeyboardButton(
                            "🔴 Disable",
                            callback_data="ab:disable",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "📜 Group Policy",
                            callback_data="ab:policy",
                        )
                    ],
                ]),
                parse_mode=ParseMode.HTML,
            )

        elif action == "mywarn":
            warnings = await get_warnings(chat_id, user_id)
            await query.answer(
                f"Your warnings: {warnings}/{WARNING_LIMIT}",
                show_alert=True,
            )

        elif action == "warnings":
            target_id = int(data[2])

            if not await is_admin(client, chat_id, user_id):
                return await query.answer(
                    "Only admins can view another user's warnings.",
                    show_alert=True,
                )

            warnings = await get_warnings(chat_id, target_id)
            await query.answer(
                f"User warnings: {warnings}/{WARNING_LIMIT}",
                show_alert=True,
            )

        elif action == "policy":
            await query.answer(
                "No abusive language, harassment or personal attacks. "
                "Repeated violations may result in a temporary mute.",
                show_alert=True,
            )

        elif action == "help":
            await query.answer(
                "/antigali - Settings\n"
                "/galiadd word - Add word\n"
                "/galidel word - Remove word\n"
                "/galiwords - List custom words\n"
                "/resetwarn - Reset warnings",
                show_alert=True,
            )

        elif action == "close":
            await query.message.delete()

        await query.answer()

    LOGGER.info("V3 MUSIC Anti-Abuse handlers registered.")
