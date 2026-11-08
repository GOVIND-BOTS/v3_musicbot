import asyncio
import logging
import os
import random
import tempfile

from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)

from .logo_generator import generate_logo, STYLES


LOGGER = logging.getLogger(__name__)

LOGO_SESSIONS = {}

STYLE_ALIASES = {
    style: style for style in STYLES
}

STYLE_ALIASES["game"] = "gaming"


def get_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✨ Next Style",
                callback_data="v3logo:next"
            ),
            InlineKeyboardButton(
                "🎲 Random",
                callback_data="v3logo:random"
            )
        ]
    ])


def create_logo_file(name, style):
    image = generate_logo(name, style)

    temp = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False
    )

    path = temp.name
    temp.close()

    try:
        image.save(
            path,
            format="PNG",
            optimize=True
        )
    finally:
        image.close()

    return path


def logo_caption(name, style):
    return (
        "✨ **Logo Generated Successfully!**\n\n"
        f"👤 **Name:** `{name}`\n"
        f"🎨 **Style:** `{style.upper()}`\n\n"
        "⚡ **Powered by V3MUSIC**"
    )


def register_logo_handlers(app):

    @app.on_message(filters.command("logo"))
    async def logo_command(client, message):

        if len(message.command) < 2:
            await message.reply_text(
                "**🎨 V3MUSIC LOGO GENERATOR**\n\n"
                "**Usage:**\n\n"
                "`/logo Govind`\n"
                "`/logo neon Govind`\n"
                "`/logo gold Govind`\n"
                "`/logo gaming Govind`\n"
                "`/logo list`\n\n"
                "✨ Generate your own stylish logo!"
            )
            return

        args = message.text.split(maxsplit=1)[1].strip()

        if args.lower() == "list":
            styles = "\n".join(
                f"• `{style}`"
                for style in STYLES
            )
            await message.reply_text(
                "**🎨 AVAILABLE LOGO STYLES**\n\n"
                f"{styles}\n\n"
                "**Example:** `/logo neon Govind`"
            )
            return

        parts = args.split(maxsplit=1)
        first = parts[0].lower()

        if first in STYLE_ALIASES:
            if len(parts) < 2 or not parts[1].strip():
                await message.reply_text(
                    f"Please provide a name.\n\n"
                    f"Example: `/logo {first} Govind`"
                )
                return
            style = STYLE_ALIASES[first]
            name = parts[1].strip()
        else:
            name = args
            style = random.choice(list(STYLES.keys()))

        name = " ".join(name.split())[:28]

        if not name:
            await message.reply_text(
                "Please provide a valid name."
            )
            return

        status = await message.reply_text(
            "🎨 **Creating your logo...**"
        )

        path = None

        try:
            path = await asyncio.to_thread(
                create_logo_file,
                name,
                style,
            )

            sent = await message.reply_photo(
                photo=path,
                caption=logo_caption(name, style),
                reply_markup=get_keyboard()
            )

            if len(LOGO_SESSIONS) > 500:
                LOGO_SESSIONS.clear()

            LOGO_SESSIONS[
                (sent.chat.id, sent.id)
            ] = {
                "name": name,
                "style": style,
                "user_id": (
                    message.from_user.id
                    if message.from_user
                    else None
                ),
            }

            await status.delete()

        except Exception as error:
            LOGGER.exception(
                "Logo generation failed: %s",
                error,
            )
            err = str(error)[:120] or type(error).__name__
            await status.edit_text(
                "❌ **Logo generation failed.**\n\n"
                f"`{err}`\n\n"
                "Check server logs / fonts / Pillow."
            )

        finally:
            if path and os.path.exists(path):
                os.remove(path)

    @app.on_callback_query(
        filters.regex(r"^v3logo:(next|random)$")
    )
    async def logo_callback(client, query):

        if not query.message:
            await query.answer(
                "Message unavailable.",
                show_alert=True
            )
            return

        key = (
            query.message.chat.id,
            query.message.id
        )

        session = LOGO_SESSIONS.get(key)

        if not session:
            await query.answer(
                "Logo session expired. Generate a new logo.",
                show_alert=True
            )
            return

        requester_id = session.get("user_id")

        if (
            requester_id
            and query.from_user.id != requester_id
        ):
            await query.answer(
                "Only the logo creator can use these buttons.",
                show_alert=True
            )
            return

        styles = list(STYLES.keys())
        current_style = session["style"]

        if query.data == "v3logo:random":
            available = [
                s for s in styles
                if s != current_style
            ]
            style = random.choice(available)
        else:
            index = styles.index(current_style)
            style = styles[(index + 1) % len(styles)]

        path = None

        try:
            path = await asyncio.to_thread(
                create_logo_file,
                session["name"],
                style,
            )

            await query.message.edit_media(
                media=InputMediaPhoto(
                    media=path,
                    caption=logo_caption(
                        session["name"],
                        style
                    )
                ),
                reply_markup=get_keyboard()
            )

            session["style"] = style

            await query.answer(
                f"New style: {style.upper()}"
            )

        except Exception:
            LOGGER.exception("Logo callback failed")
            await query.answer(
                "Unable to generate logo.",
                show_alert=True
            )

        finally:
            if path and os.path.exists(path):
                os.remove(path)
