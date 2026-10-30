
import logging
import os
import tempfile
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont
from pyrogram import filters
from pyrogram.enums import ParseMode

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
WELCOME_IMAGE = BASE_DIR / "assets" / "welcome.png"


def get_font(size):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]

    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def fit_font(draw, text, max_width, size=29):
    while size > 14:
        font = get_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)

        if bbox[2] - bbox[0] <= max_width:
            return font

        size -= 1

    return get_font(14)


def create_welcome_image(user_photo, user, chat):
    image = Image.open(WELCOME_IMAGE).convert("RGBA")
    draw = ImageDraw.Draw(image)

    # -----------------------------
    # MEMBER PROFILE PHOTO
    # -----------------------------
    if user_photo and os.path.isfile(user_photo):
        avatar = Image.open(user_photo).convert("RGB")

        width, height = avatar.size
        crop = min(width, height)

        left = (width - crop) // 2
        top = (height - crop) // 2

        avatar = avatar.crop((
            left,
            top,
            left + crop,
            top + crop,
        ))

        diameter = 380

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

        x = 440 - diameter // 2
        y = 445 - diameter // 2

        image.paste(avatar, (x, y), mask)

    # -----------------------------
    # MEMBER INFORMATION
    # -----------------------------
    name = " ".join(
        part for part in [
            user.first_name,
            user.last_name,
        ] if part
    ).strip() or "Unknown"

    user_id = str(user.id)

    username = (
        f"@{user.username}"
        if user.username
        else "Not set"
    )

    group_name = chat.title or "Unknown Group"

    try:
        joined_date = datetime.now(
            ZoneInfo("Asia/Kolkata")
        ).strftime("%d %b %Y")
    except Exception:
        joined_date = datetime.now().strftime("%d %b %Y")

    # Cover old fixed values from the template.
    rows = [
        (1080, 285, 1470, 350),
        (1080, 350, 1470, 415),
        (1080, 415, 1470, 480),
        (1080, 480, 1470, 545),
        (1080, 545, 1470, 605),
    ]

    for x1, y1, x2, y2 in rows:
        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=8,
            fill=(5, 3, 24, 235),
        )

    # Text positions and neon colors.
    fields = [
        (name, 1093, 299, (0, 210, 255, 255)),
        (user_id, 1093, 364, (255, 45, 230, 255)),
        (username, 1093, 429, (0, 255, 210, 255)),
        (group_name, 1093, 494, (255, 190, 30, 255)),
        (joined_date, 1093, 559, (255, 65, 220, 255)),
    ]

    draw = ImageDraw.Draw(image)

    for text, x, y, color in fields:
        font = fit_font(
            draw,
            text,
            max_width=350,
            size=29,
        )

        # Small dark outline for readability.
        draw.text(
            (x, y),
            text,
            font=font,
            fill=color,
            stroke_width=1,
            stroke_fill=(10, 0, 25, 255),
        )

    output = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
    )

    output_path = output.name
    output.close()

    image.convert("RGB").save(
        output_path,
        format="PNG",
    )

    return output_path


def register_welcome_handlers(app):

    @app.on_message(
        filters.group & filters.new_chat_members
    )
    async def welcome_new_members(client, message):

        if not WELCOME_IMAGE.exists():
            LOGGER.error(
                "Welcome image not found: %s",
                WELCOME_IMAGE,
            )
            return

        for user in message.new_chat_members:

            photo_path = None
            output_path = None

            try:
                # Download joining member's actual DP.
                if user.photo:
                    photo_path = await client.download_media(
                        user.photo.big_file_id
                    )

                # Generate personalized welcome image.
                output_path = create_welcome_image(
                    photo_path,
                    user,
                    message.chat,
                )

                name = " ".join(
                    part for part in [
                        user.first_name,
                        user.last_name,
                    ] if part
                ).strip() or "Member"

                mention = (
                    f'<a href="tg://user?id={user.id}">'
                    f'{html_escape(name)}</a>'
                )

                caption = (
                    "✨ <b>WELCOME TO THE GROUP!</b> ✨\n\n"
                    f"👑 Hello {mention}!\n"
                    f"💖 Welcome to "
                    f"<b>{html_escape(message.chat.title or 'Our Group')}</b>\n\n"
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
                    "Welcome sent to user %s",
                    user.id,
                )

            except Exception:
                LOGGER.exception(
                    "Welcome error for user %s",
                    user.id,
                )

            finally:
                for path in (photo_path, output_path):
                    if path and os.path.isfile(path):
                        try:
                            os.remove(path)
                        except OSError:
                            pass

    LOGGER.info("Welcome handlers registered.")


def html_escape(text):
    import html
    return html.escape(str(text))
