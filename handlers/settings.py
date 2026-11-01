
import logging

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from database.mongodb import get_chat_settings, update_chat_settings
from player_ui import stylize


LOGGER = logging.getLogger(__name__)


DEFAULT_SETTINGS = {
    "audio_quality": "HIGH",
    "video_quality": "480p",
    "play_mode": "QUEUE",
    "clean_mode": False,
    "authorized_users": [],
}

AUDIO_QUALITIES = ("LOW", "MEDIUM", "HIGH")
VIDEO_QUALITIES = ("360p", "480p", "720p")
PLAY_MODES = ("QUEUE", "SEQUENTIAL")


async def is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )
    except Exception:
        return False


async def load_settings(chat_id):
    try:
        settings = await get_chat_settings(chat_id)
    except Exception:
        LOGGER.exception("Unable to load chat settings")
        settings = {}

    result = DEFAULT_SETTINGS.copy()
    result.update(settings)

    if not isinstance(result.get("authorized_users"), list):
        result["authorized_users"] = []

    return result


async def save_setting(chat_id, key, value):
    await update_chat_settings(chat_id, key, value)


def settings_text(settings):
    audio = settings["audio_quality"]
    video = settings["video_quality"]
    mode = settings["play_mode"]
    clean = "ON" if settings["clean_mode"] else "OFF"
    authorized = len(settings["authorized_users"])

    return (
        f"⚙️ {stylize('Adisha Music Settings')}\n\n"
        f"🎵 {stylize('Audio Quality:')} "
        f"<code>{audio}</code>\n"
        f"🎬 {stylize('Video Quality:')} "
        f"<code>{video}</code>\n"
        f"▶️ {stylize('Play Mode:')} "
        f"<code>{mode}</code>\n"
        f"🧹 {stylize('Clean Mode:')} "
        f"<code>{clean}</code>\n"
        f"👥 {stylize('Authorized Users:')} "
        f"<code>{authorized}</code>\n\n"
        f"{stylize('Choose a setting below to configure it.')}"
    )


def settings_keyboard(settings):
    clean_label = (
        "🟢 Clean Mode: ON"
        if settings["clean_mode"]
        else "🔴 Clean Mode: OFF"
    )

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🎵 Audio Quality",
                callback_data="settings_audio",
            ),
            InlineKeyboardButton(
                "🎬 Video Quality",
                callback_data="settings_video",
            ),
        ],
        [
            InlineKeyboardButton(
                "▶️ Play Mode",
                callback_data="settings_playmode",
            ),
        ],
        [
            InlineKeyboardButton(
                clean_label,
                callback_data="settings_clean",
            ),
        ],
        [
            InlineKeyboardButton(
                "👥 Authorized Users",
                callback_data="settings_auth",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="settings_home",
            ),
            InlineKeyboardButton(
                "✖ Close",
                callback_data="settings_close",
            ),
        ],
    ])


def option_keyboard(title, options, selected, prefix):
    rows = []

    for option in options:
        label = f"✓ {option}" if option == selected else option

        rows.append([
            InlineKeyboardButton(
                label,
                callback_data=f"{prefix}_{option}",
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="settings_home",
        )
    ])

    return InlineKeyboardMarkup(rows)


def authorized_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ Add User",
                callback_data="settings_authadd",
            ),
            InlineKeyboardButton(
                "➖ Remove User",
                callback_data="settings_authremove",
            ),
        ],
        [
            InlineKeyboardButton(
                "📋 View Users",
                callback_data="settings_authlist",
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="settings_home",
            ),
        ],
    ])


def register_settings_handlers(app):

    @app.on_message(filters.command("settings") & filters.group)
    async def settings_command(client, message):
        if not message.from_user:
            return

        if not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text(
                stylize("Only group admins can access settings.")
            )

        settings = await load_settings(message.chat.id)

        await message.reply_text(
            settings_text(settings),
            reply_markup=settings_keyboard(settings),
            parse_mode=ParseMode.HTML,
        )

    @app.on_message(filters.command("authadd") & filters.group)
    async def auth_add_command(client, message):
        if not message.from_user:
            return

        if not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text(
                stylize("Only group admins can manage authorized users.")
            )

        args = message.text.split(maxsplit=1)

        if len(args) < 2 or not args[1].strip().lstrip("-").isdigit():
            return await message.reply_text(
                f"{stylize('Usage:')} <code>/authadd USER_ID</code>",
                parse_mode=ParseMode.HTML,
            )

        user_id = int(args[1].strip())
        settings = await load_settings(message.chat.id)
        users = settings["authorized_users"]

        if user_id in users:
            return await message.reply_text(
                stylize("This user is already authorized.")
            )

        users.append(user_id)
        await save_setting(
            message.chat.id,
            "authorized_users",
            users,
        )

        await message.reply_text(
            f"✅ {stylize('User authorized successfully.')}\n"
            f"<code>{user_id}</code>",
            parse_mode=ParseMode.HTML,
        )

    @app.on_message(filters.command("authremove") & filters.group)
    async def auth_remove_command(client, message):
        if not message.from_user:
            return

        if not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text(
                stylize("Only group admins can manage authorized users.")
            )

        args = message.text.split(maxsplit=1)

        if len(args) < 2 or not args[1].strip().lstrip("-").isdigit():
            return await message.reply_text(
                f"{stylize('Usage:')} <code>/authremove USER_ID</code>",
                parse_mode=ParseMode.HTML,
            )

        user_id = int(args[1].strip())
        settings = await load_settings(message.chat.id)
        users = settings["authorized_users"]

        if user_id not in users:
            return await message.reply_text(
                stylize("This user is not in the authorized list.")
            )

        users.remove(user_id)

        await save_setting(
            message.chat.id,
            "authorized_users",
            users,
        )

        await message.reply_text(
            stylize("User authorization removed successfully.")
        )

    @app.on_message(filters.command("authlist") & filters.group)
    async def auth_list_command(client, message):
        if not message.from_user:
            return

        if not await is_admin(
            client,
            message.chat.id,
            message.from_user.id,
        ):
            return await message.reply_text(
                stylize("Only group admins can view authorized users.")
            )

        settings = await load_settings(message.chat.id)
        users = settings["authorized_users"]

        if not users:
            return await message.reply_text(
                stylize("No authorized users found.")
            )

        lines = [f"👥 {stylize('Authorized Users')}"]

        for index, user_id in enumerate(users, start=1):
            lines.append(f"\n<code>{index}.</code> <code>{user_id}</code>")

        await message.reply_text(
            "".join(lines),
            parse_mode=ParseMode.HTML,
        )

    @app.on_callback_query(filters.regex(r"^settings_"))
    async def settings_callback(client, callback):
        if not callback.message:
            return await callback.answer()

        chat_id = callback.message.chat.id
        user = callback.from_user

        if not await is_admin(client, chat_id, user.id):
            return await callback.answer(
                "Only group admins can change settings.",
                show_alert=True,
            )

        data = callback.data
        settings = await load_settings(chat_id)

        try:
            if data == "settings_close":
                await callback.message.delete()
                return await callback.answer()

            if data == "settings_home":
                await callback.message.edit_text(
                    settings_text(settings),
                    reply_markup=settings_keyboard(settings),
                    parse_mode=ParseMode.HTML,
                )
                return await callback.answer()

            if data == "settings_audio":
                await callback.message.edit_text(
                    f"🎵 {stylize('Select Audio Quality')}",
                    reply_markup=option_keyboard(
                        "Audio Quality",
                        AUDIO_QUALITIES,
                        settings["audio_quality"],
                        "settings_setaudio",
                    ),
                    parse_mode=ParseMode.HTML,
                )
                return await callback.answer()

            if data == "settings_video":
                await callback.message.edit_text(
                    f"🎬 {stylize('Select Video Quality')}",
                    reply_markup=option_keyboard(
                        "Video Quality",
                        VIDEO_QUALITIES,
                        settings["video_quality"],
                        "settings_setvideo",
                    ),
                    parse_mode=ParseMode.HTML,
                )
                return await callback.answer()

            if data == "settings_playmode":
                await callback.message.edit_text(
                    f"▶️ {stylize('Select Play Mode')}",
                    reply_markup=option_keyboard(
                        "Play Mode",
                        PLAY_MODES,
                        settings["play_mode"],
                        "settings_setmode",
                    ),
                    parse_mode=ParseMode.HTML,
                )
                return await callback.answer()

            if data == "settings_clean":
                new_value = not settings["clean_mode"]

                await save_setting(
                    chat_id,
                    "clean_mode",
                    new_value,
                )

                settings["clean_mode"] = new_value

                await callback.message.edit_text(
                    settings_text(settings),
                    reply_markup=settings_keyboard(settings),
                    parse_mode=ParseMode.HTML,
                )
                return await callback.answer("Clean Mode updated.")

            if data == "settings_auth":
                await callback.message.edit_text(
                    f"👥 {stylize('Authorized Users')}\n\n"
                    f"{stylize('Use these commands:')}\n"
                    f"<code>/authadd USER_ID</code>\n"
                    f"<code>/authremove USER_ID</code>\n"
                    f"<code>/authlist</code>",
                    reply_markup=authorized_keyboard(),
                    parse_mode=ParseMode.HTML,
                )
                return await callback.answer()

            if data == "settings_authadd":
                await callback.answer(
                    "Use /authadd USER_ID in the group.",
                    show_alert=True,
                )
                return

            if data == "settings_authremove":
                await callback.answer(
                    "Use /authremove USER_ID in the group.",
                    show_alert=True,
                )
                return

            if data == "settings_authlist":
                users = settings["authorized_users"]

                if not users:
                    text = stylize("No authorized users found.")
                else:
                    text = (
                        f"👥 {stylize('Authorized Users')}\n\n"
                        + "\n".join(
                            f"<code>{user_id}</code>"
                            for user_id in users
                        )
                    )

                await callback.message.edit_text(
                    text,
                    reply_markup=authorized_keyboard(),
                    parse_mode=ParseMode.HTML,
                )
                return await callback.answer()

            if data.startswith("settings_setaudio_"):
                value = data.replace("settings_setaudio_", "", 1)

                if value not in AUDIO_QUALITIES:
                    return await callback.answer(
                        "Invalid audio quality.",
                        show_alert=True,
                    )

                await save_setting(chat_id, "audio_quality", value)

            elif data.startswith("settings_setvideo_"):
                value = data.replace("settings_setvideo_", "", 1)

                if value not in VIDEO_QUALITIES:
                    return await callback.answer(
                        "Invalid video quality.",
                        show_alert=True,
                    )

                await save_setting(chat_id, "video_quality", value)

            elif data.startswith("settings_setmode_"):
                value = data.replace("settings_setmode_", "", 1)

                if value not in PLAY_MODES:
                    return await callback.answer(
                        "Invalid play mode.",
                        show_alert=True,
                    )

                await save_setting(chat_id, "play_mode", value)

            else:
                return await callback.answer()

            settings = await load_settings(chat_id)

            await callback.message.edit_text(
                settings_text(settings),
                reply_markup=settings_keyboard(settings),
                parse_mode=ParseMode.HTML,
            )

            await callback.answer("Setting updated successfully.")

        except Exception:
            LOGGER.exception("Settings callback failed")
            await callback.answer(
                "Unable to update settings. Please try again.",
                show_alert=True,
            )

    LOGGER.info("Settings handlers registered")
