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

from .logo_generator import generate_ai_logo, generate_logo, STYLES


LOGGER = logging.getLogger(__name__)

LOGO_SESSIONS = {}

STYLE_ALIASES = {style: style for style in STYLES}
STYLE_ALIASES["game"] = "gaming"


def get_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✨ Next Style", callback_data="v3logo:next"),
            InlineKeyboardButton("🎲 Random", callback_data="v3logo:random"),
        ]
    ])


def create_logo_file(name, style):
    temp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    path = temp.name
    temp.close()

    try:
        if os.getenv("OPENAI_API_KEY", "").strip():
            image_bytes = generate_ai_logo(name, style)
            with open(path, "wb") as output:
                output.write(image_bytes)
        else:
            image = generate_logo(name, style)
            try:
                image.save(path, format="PNG", optimize=True)
            finally:
                image.close()
        return path
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise


def logo_caption(name, style):
    return (
        "✨ **Logo Generated Successfully!**\n\n"
        f"👤 **Name:** `{name}`\n"
        f"🎨 **Style:** `{style.upper()}`\n\n"
        "⚡ **Powered by V3MUSIC**"
    )


def register_logo_handlers(app):

    # Keep this command in its own earlier handler group. Pyrogram runs only
    # the first matching handler in a group; generic message handlers registered
    # before this module could otherwise swallow /logo without replying.
    @app.on_message(filters.command("logo"), group=-1)
    async def logo_command(client, message):
        command = getattr(message, "command", None) or []
        args = " ".join(command[1:]).strip()

        if not args:
            return await message.reply_text(
                "**🎨 V3MUSIC LOGO GENERATOR**\n\n"
                "**Usage:**\n\n"
                "`/logo Govind`\n"
                "`/logo neon Govind`\n"
                "`/logo gold Govind`\n"
                "`/logo gaming Govind`\n"
                "`/logo list`\n\n"
                "✨ Generate your own stylish logo!"
            )

        if args.lower() == "list":
            styles = "\n".join(f"• `{style}`" for style in STYLES)
            return await message.reply_text(
                "**🎨 AVAILABLE LOGO STYLES**\n\n"
                f"{styles}\n\n"
                "**Example:** `/logo neon Govind`"
            )

        parts = args.split(maxsplit=1)
        first = parts[0].lower()

        if first in STYLE_ALIASES:
            if len(parts) < 2 or not parts[1].strip():
                return await message.reply_text(
                    f"Please provide a name.\n\nExample: `/logo {first} Govind`"
                )
            style = STYLE_ALIASES[first]
            name = parts[1].strip()
        else:
            name = args
            style = random.choice(tuple(STYLES))

        name = " ".join(name.split())[:28]
        if not name:
            return await message.reply_text("Please provide a valid name.")

        status = await message.reply_text("🎨 **Creating your logo...**")
        path = None

        try:
            path = await asyncio.to_thread(create_logo_file, name, style)
            sent = await message.reply_photo(
                photo=path,
                caption=logo_caption(name, style),
                reply_markup=get_keyboard(),
            )

            if len(LOGO_SESSIONS) >= 500:
                LOGO_SESSIONS.clear()

            LOGO_SESSIONS[(sent.chat.id, sent.id)] = {
                "name": name,
                "style": style,
                "user_id": message.from_user.id if message.from_user else None,
            }
            await status.delete()

        except Exception as error:
            LOGGER.exception("Logo generation/send failed")
            err = str(error)[:180] or type(error).__name__
            try:
                await status.edit_text(
                    "❌ **Logo generation failed.**\n\n"
                    f"`{err}`\n\n"
                    "Check the Railway log for the full traceback."
                )
            except Exception:
                LOGGER.exception("Could not display logo error")

        finally:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    LOGGER.warning("Could not remove temporary logo file: %s", path)

    @app.on_callback_query(
        filters.regex(r"^v3logo:(next|random)$"),
        group=-1,
    )
    async def logo_callback(client, query):
        if not query.message:
            return await query.answer("Message unavailable.", show_alert=True)

        key = (query.message.chat.id, query.message.id)
        session = LOGO_SESSIONS.get(key)

        if not session:
            return await query.answer(
                "Logo session expired. Generate a new logo.",
                show_alert=True,
            )

        requester_id = session.get("user_id")
        if requester_id and query.from_user.id != requester_id:
            return await query.answer(
                "Only the logo creator can use these buttons.",
                show_alert=True,
            )

        styles = list(STYLES)
        current_style = session["style"]

        if query.data == "v3logo:random":
            available = [style for style in styles if style != current_style]
            style = random.choice(available or styles)
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
                    caption=logo_caption(session["name"], style),
                ),
                reply_markup=get_keyboard(),
            )
            session["style"] = style
            await query.answer(f"New style: {style.upper()}")

        except Exception:
            LOGGER.exception("Logo style callback failed")
            await query.answer("Unable to generate logo.", show_alert=True)

        finally:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    LOGGER.warning("Could not remove temporary logo file: %s", path)

    LOGGER.info("Logo command and callbacks registered (handler group -1).")
