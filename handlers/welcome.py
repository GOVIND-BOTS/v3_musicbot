
import os
import html
import logging
import tempfile

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from pyrogram import filters
from pyrogram.enums import ParseMode


LOGGER = logging.getLogger(__name__)

# Background image location
BASE_DIR = Path(__file__).resolve().parent.parent
WELCOME_IMAGE = BASE_DIR / "assets" / "welcome.png"


def get_font(size):
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    try:
        return ImageFont.truetype(font_path, size)
    except OSError:
        return ImageFont.load_default()


def create_welcome_image(user_photo, user_name):
    background = Image.open(WELCOME_IMAGE).convert("RGBA")

    # Circular profile photo
    if user_photo:
        avatar = Image.open(user_photo).convert("RGB")

        diameter = 510

        width, height = avatar.size
        crop_size = min(width, height)

        left = (width - crop_size) // 2
        top = (height - crop_size) // 2

        avatar = avatar.crop((
            left,
            top,
            left + crop_size,
            top + crop_size,
        ))

        avatar = avatar.resize(
            (diameter, diameter),
            Image.Resampling.LANCZOS,
        )

        mask = Image.new("L", (diameter, diameter), 0)
        mask_draw = ImageDraw.Draw(mask)

        mask_draw.ellipse(
            (0, 0, diameter - 1, diameter - 1),
            fill=255,
        )

        
        x = 489 - diameter // 2
        y = 465 - diameter // 2

        background.paste(
            avatar,
            (x, y),
            mask,
        )

    
    draw = ImageDraw.Draw(background)

    name = user_name.strip() or "New Member"
    name = name[:24]

    font = get_font(48)

    
    while draw.textbbox((0, 0), name, font=font)[2] > 680:
        font = get_font(max(20, font.size - 3))

    name_x = 905
    name_y = 395


    glow_draw.text(
        (name_x, name_y),
        name,
        font=font,
        fill=(255, 0, 200, 255),
        stroke_width=2,
    )

    glow = glow.filter(
        ImageFilter.GaussianBlur(12)
    )

    background = Image.alpha_composite(
        background,
        glow,
    )

    draw = ImageDraw.Draw(background)

    # Colorful name
    draw.text(
        (name_x, name_y),
        name,
        font=font,
        fill=(255, 255, 255, 255),
        stroke_width=2,
        stroke_fill=(255, 0, 200, 255),
    )

    subtitle_font = get_font(25)

    draw.text(
        (name_x, name_y + 75),
        "JUST JOINED THE GROUP",
        font=subtitle_font,
        fill=(0, 220, 255, 255),
        stroke_width=1,
        stroke_fill=(120, 0, 255, 255),
    )

    
    temp = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
    )

    output_path = temp.name
    temp.close()

    background.convert("RGB").save(
        output_path,
        quality=95,
    )

    return output_path


def register_welcome_handlers(app):

    @app.on_message(
        filters.new_chat_members & filters.group
    )
    async def welcome_new_members(client, message):

        if not WELCOME_IMAGE.exists():
            LOGGER.error(
                "Welcome background not found: %s",
                WELCOME_IMAGE,
            )
            return

        for user in message.new_chat_members:

            user_name = user.first_name or "New Member"

            photo_path = None
            output_path = None

            try:
                # Get user's profile photo
                photos = await client.get_profile_photos(
                    user.id,
                    limit=1,
                )

                if photos:
                    photo_path = await client.download_media(
                        photos[0].file_id
                    )

                # Generate welcome image
                output_path = create_welcome_image(
                    photo_path,
                    user_name,
                )

                mention = (
                    f'<a href="tg://user?id={user.id}">'
                    f'{html.escape(user_name)}</a>'
                )

                caption = (
                    "✨ <b>WELCOME TO THE GROUP!</b> ✨\n\n"
                    f"👑 Hello {mention}!\n"
                    f"💖 Welcome to "
                    f"<b>{html.escape(message.chat.title or 'Our Group')}</b>\n\n"
                    "🌸 We are happy to have you here!\n"
                    "🤝 Enjoy your time with us.\n\n"
                    "💫 <b>GOVIND OP</b>"
                )

                await message.reply_photo(
                    photo=output_path,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                )

                LOGGER.info(
                    "Welcome sent to %s in %s",
                    user.id,
                    message.chat.id,
                )

            except Exception:
                LOGGER.exception(
                    "Welcome failed for user %s",
                    user.id,
                )

            finally:
                for path in (photo_path, output_path):
                    if path and os.path.isfile(path):
                        try:
                            os.remove(path)
                        except OSError:
                            pass
